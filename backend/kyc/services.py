"""KYC service: the backend-authoritative verification engine.

Only this module (and the authorised review views that call it) transitions
``KYCProfile`` state. The frontend submits requests and reads status; it can
never write ``verification_status`` directly.

Golden chain enforced here:

    MEMBER -> REQUEST -> PROVIDER -> RESPONSE -> validation
            -> profile STATUS -> audit event -> eligibility flag
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from kyc.models import KYCProfile, KYCEvent, KYCVerificationRequest
from kyc.providers import get_provider
from kyc.providers.base import ProviderOutcome
from kyc.statuses import KYCLevel, KYCStatus, KYCVerificationMethod, RequestStatus

REQUIRED_LEVEL_DEFAULT = KYCLevel.LEVEL_1


class KYCError(Exception):
    """Raised for business-rule violations (mapped to HTTP 400 in views)."""


def _setting(*attrs, default=None):
    for attr in attrs:
        value = getattr(settings, attr, None)
        if value not in (None, ""):
            return value
    return default


def verification_expiry_days():
    return int(_setting("KYC_VERIFICATION_EXPIRY_DAYS", default=365))


def max_attempts():
    return int(_setting("KYC_MAX_ATTEMPTS", default=3))


def required_level_default():
    return str(_setting("KYC_REQUIRED_LEVEL", default=REQUIRED_LEVEL_DEFAULT))


# --------------------------------------------------------------------------- #
# Profile lifecycle
# --------------------------------------------------------------------------- #

def get_or_create_profile(member) -> KYCProfile:
    profile, _created = KYCProfile.objects.get_or_create(member=member)
    if member.is_verified and profile.status != KYCStatus.VERIFIED:
        # A member verified through the legacy manual pipeline must map into an
        # explicit, audited VERIFIED profile (LEVEL_1) — lazily and idempotently.
        sync_from_member(member)
        profile.refresh_from_db()
    return profile


def record_event(
    profile,
    *,
    action,
    request=None,
    from_status="",
    to_status="",
    status="",
    provider="",
    provider_reference="",
    failure_code="",
    actor=None,
    actor_type=KYCEvent.ACTOR_SYSTEM,
    ip_address=None,
    metadata=None,
):
    return KYCEvent.objects.create(
        profile=profile,
        request=request,
        action=action,
        status=status or (profile.status if profile.pk else ""),
        from_status=from_status,
        to_status=to_status,
        provider=provider or (getattr(request, "provider", "") if request else ""),
        provider_reference=(
            provider_reference
            or (getattr(request, "provider_reference", "") or "")
        ),
        failure_code=failure_code,
        actor=actor,
        actor_type=actor_type,
        ip_address=ip_address,
        metadata=metadata or {},
    )


def _change_status(profile, to_status, *, from_status, actor=None, ip_address=None, reason=""):
    """Apply a profile transition (validated) and write the audit event."""
    if profile.status == to_status:
        return False
    if not profile.can_transition(to_status):
        raise KYCError(
            f"Illegal KYC state transition {profile.status} -> {to_status}. "
            "The backend verification process or an authorized reviewer controls KYC status."
        )
    profile.status = to_status
    profile.updated_at = timezone.now()
    record_event(
        profile,
        action=KYCEvent.ACTION_STATUS_CHANGED,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
        metadata={"reason": reason} if reason else {},
    )
    return True


def sync_from_member(member, *, actor=None, ip_address=None):
    """Reconcile the KYC profile with the existing manual Member pipeline.

    Called from ``Member.refresh_verification`` so the legacy manual-review
    boolean (documents staff-verified + phone + next of kin + submission) is
    reflected as an explicit, audited VERIFIED profile at LEVEL_1. Staff-created
    members (auto-verified) land here the same way. Upgrades to a provider level
    are handled by :func:`submit_verification`.
    """
    profile, _created = KYCProfile.objects.get_or_create(member=member)
    if member.is_verified and profile.status != KYCStatus.VERIFIED:
        if not profile.can_transition(KYCStatus.VERIFIED):
            return profile
        from_status = profile.status
        before = (profile.status, profile.verification_level)
        profile.status = KYCStatus.VERIFIED
        profile.verification_level = KYCLevel.LEVEL_1
        profile.verification_method = _merge_method(
            profile.verification_method, KYCVerificationMethod.MANUAL_REVIEW
        )
        profile.last_checked_at = timezone.now()
        if not profile.expires_at:
            profile.expires_at = timezone.now() + timedelta(days=verification_expiry_days())
        profile.save(
            update_fields=[
                "status", "verification_level", "verification_method",
                "last_checked_at", "expires_at", "updated_at",
            ]
        )
        record_event(
            profile,
            action=KYCEvent.ACTION_SYNCED_FROM_MEMBER,
            from_status=from_status,
            to_status=KYCStatus.VERIFIED,
            actor=actor,
            actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
            ip_address=ip_address,
            metadata={"raised_from_level_before": before},
        )
    return profile


def _merge_method(current, incoming):
    if current in (KYCVerificationMethod.NONE, "", None):
        return incoming
    if current == incoming:
        return current
    return KYCVerificationMethod.BOTH


def check_expiry(profile, *, actor=None, ip_address=None) -> bool:
    """Sweep for expired verifications. Returns True when status changed."""
    if profile.status == KYCStatus.VERIFIED and profile.expired:
        from_status = profile.status
        profile.status = KYCStatus.EXPIRED
        profile.failure_code = "VERIFICATION_EXPIRED"
        profile.save(update_fields=["status", "failure_code", "updated_at"])
        record_event(
            profile,
            action=KYCEvent.ACTION_EXPIRED,
            from_status=from_status,
            to_status=KYCStatus.EXPIRED,
            failure_code="VERIFICATION_EXPIRED",
            actor=actor,
            ip_address=ip_address,
        )
        return True
    return False


# --------------------------------------------------------------------------- #
# Eligibility (consumed by withdrawal + loan engines)
# --------------------------------------------------------------------------- #

def satisfies(member, required_level: str | None = None) -> bool:
    """True when the member's KYC satisfies ``required_level``.

    ``required_level`` defaults to the platform setting ``KYC_REQUIRED_LEVEL``
    (LEVEL_1). LEVEL_0 always passes. Expired verifications never satisfy.
    """
    required = required_level or required_level_default()
    if required == KYCLevel.LEVEL_0:
        return True
    profile = get_or_create_profile(member)
    check_expiry(profile)
    if profile.status != KYCStatus.VERIFIED:
        return False
    if profile.expired:
        return False
    return KYCLevel.at_least(profile.verification_level, required)


def current_status(member) -> dict:
    """Member-safe summary used by /kyc/me/ and profile serializers."""
    profile = get_or_create_profile(member)
    check_expiry(profile)
    from kyc.utils import mask_identifier

    full_name = f"{member.first_name or ''} {member.last_name or ''}".strip()
    return {
        "status": profile.status,
        "verification_level": profile.verification_level,
        "verification_method": profile.verification_method,
        "provider": profile.provider,
        "provider_reference": mask_identifier(profile.provider_reference, keep=6),
        "verified_at": profile.verified_at,
        "expires_at": profile.expires_at,
        "last_checked_at": profile.last_checked_at,
        "failure_code": profile.failure_code,
        "failure_reason": profile.failure_reason,
        "identity_summary": _identity_summary(member, full_name),
        "required_level": required_level_default(),
        "eligible": satisfies(member),
        "eligible_level_2": satisfies(member, KYCLevel.LEVEL_2),
    }


def _identity_summary(member, full_name):
    from kyc.utils import mask_identifier

    return {
        "full_name": full_name,
        "national_id": mask_identifier(member.national_id, keep=4),
        "date_of_birth": str(member.date_of_birth) if member.date_of_birth else "",
        "complete": bool(member.national_id and member.date_of_birth and full_name),
    }


# --------------------------------------------------------------------------- #
# Verification request flow
# --------------------------------------------------------------------------- #

def _member_identity(member):
    """Pull the identity values a provider call needs from the Member record.

    The member profile owns this data (data minimisation: KYC does not duplicate
    it). Returns ``(national_id, full_name, date_of_birth)``.
    """
    full_name = f"{member.first_name or ''} {member.last_name or ''}".strip()
    dob = member.date_of_birth or ""
    if dob and not isinstance(dob, str):
        dob = dob.isoformat()
    if not member.national_id or not dob or not full_name:
        raise KYCError(
            "Complete your identity profile (full name, national ID and date of birth) "
            "before starting verification."
        )
    return member.national_id, full_name, dob


def submit_verification(
    *,
    member,
    idempotency_key=None,
    actor=None,
    ip_address=None,
) -> dict:
    """Submit (or safely resubmit) one identity verification.

    Idempotency / flooding control:
    - at most one in-flight request per member (DB-enforced unique constraint);
    - a request already SUCCESS is returned as-is (no new provider call);
    - a request with the same ``idempotency_key`` is returned as-is;
    - a REJECTED request is terminal and requires an authorised review action;
    - a PROVIDER_ERROR request may be retried up to ``max_attempts`` times by
      re-submission (provider failure != identity failure, section 18-19).

    Returns ``{"profile": ..., "request": ...}``. Never marks a member VERIFIED
    without an authoritative provider response.
    """
    profile = get_or_create_profile(member)
    check_expiry(profile)

    active = (
        KYCVerificationRequest.objects.filter(profile=profile)
        .filter(status__in=["SUBMITTED", "PROCESSING"])
        .first()
    )
    if active is not None:
        return {"profile": profile, "request": active}

    if idempotency_key:
        existing = (
            KYCVerificationRequest.objects.filter(idempotency_key=idempotency_key, profile=profile).first()
        )
        if existing is not None and existing.status not in ("SUBMITTED", "PROCESSING"):
            return {"profile": profile, "request": existing}

    if profile.status == KYCStatus.VERIFIED and not profile.expired:
        last = profile.requests.filter(status=RequestStatus.SUCCESS).first()
        return {"profile": profile, "request": last}

    if profile.status == KYCStatus.REJECTED:
        raise KYCError(
            "Your last verification attempt was rejected. A verified reviewer must "
            "reopen your case before you can submit again."
        )

    national_id, full_name, dob_iso = _member_identity(member)

    # A new attempt may retry a PROVIDER_ERROR request (bounded) or start fresh.
    request = KYCVerificationRequest.objects.create(
        profile=profile,
        idempotency_key=idempotency_key,
        status=RequestStatus.SUBMITTED,
        attempt_count=1,
        max_attempts=max_attempts(),
    )
    record_event(
        profile,
        request=request,
        action=KYCEvent.ACTION_REQUEST_STARTED,
        from_status=profile.status,
        to_status=RequestStatus.SUBMITTED,
        actor=actor,
        actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
    )

    _run_provider(request, profile, national_id, full_name, dob_iso, actor=actor, ip_address=ip_address)
    return {"profile": profile, "request": request}


def retry_verification(*, member, idempotency_key=None, actor=None, ip_address=None) -> dict:
    """Retry the latest PROVIDER_ERROR attempt if attempts remain (bounded)."""
    profile = get_or_create_profile(member)
    latest = profile.requests.filter(status=RequestStatus.PROVIDER_ERROR).order_by("-submitted_at").first()
    if latest is None:
        raise KYCError("There is no provider-error attempt to retry.")
    if latest.attempt_count >= latest.max_attempts:
        raise KYCError("Maximum verification attempts reached. Contact an administrator.")
    if latest.idempotency_key and idempotency_key and latest.idempotency_key != idempotency_key:
        raise KYCError("Idempotency key mismatch for this attempt.")

    national_id, full_name, dob_iso = _member_identity(member)
    latest.attempt_count += 1
    latest.status = RequestStatus.SUBMITTED
    latest.save(update_fields=["attempt_count", "status"])

    record_event(
        profile,
        request=latest,
        action=KYCEvent.ACTION_RETRY,
        from_status=RequestStatus.PROVIDER_ERROR,
        to_status=RequestStatus.SUBMITTED,
        actor=actor,
        actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
        metadata={"attempt": latest.attempt_count, "max_attempts": latest.max_attempts},
    )
    _run_provider(latest, profile, national_id, full_name, dob_iso, actor=actor, ip_address=ip_address)
    return {"profile": profile, "request": latest}


def _run_provider(request, profile, national_id, full_name, dob_iso, *, actor=None, ip_address=None):
    """Call the configured provider and apply its authoritative outcome."""
    provider = get_provider()
    if provider is None or not provider.is_available():
        _mark_provider_error(
            request, profile,
            failure_code="PROVIDER_UNAVAILABLE",
            reason="Identity verification service is not configured or unavailable.",
            actor=actor, ip_address=ip_address,
        )
        return None

    request.provider = provider.provider_id
    request.save(update_fields=["provider"])
    record_event(
        profile, request=request, action=KYCEvent.ACTION_PROVIDER_REQUEST,
        provider=provider.provider_id, actor=actor,
        actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
        metadata={"attempt": request.attempt_count},
    )

    try:
        response = provider.verify_identity(
            national_id=national_id, full_name=full_name, date_of_birth=dob_iso
        )
    except Exception as exc:  # noqa: BLE001 - provider failures are handled, never raised at the client
        _mark_provider_error(
            request, profile,
            failure_code="PROVIDER_EXCEPTION",
            reason=str(exc.__class__.__name__) or "Provider exception.",
            actor=actor, ip_address=ip_address,
        )
        return None

    if not response or not response.outcome:
        _mark_provider_error(
            request, profile,
            failure_code="INVALID_PROVIDER_RESPONSE",
            reason="Provider returned an empty or malformed response.",
            actor=actor, ip_address=ip_address,
        )
        return None

    record_event(
        profile, request=request, action=KYCEvent.ACTION_PROVIDER_RESPONSE,
        provider=request.provider,
        provider_reference=response.provider_reference or "",
        actor=actor,
        actor_type=KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
        status=response.outcome,
        metadata={"outcome": response.outcome},
    )

    if request.status not in ("SUBMITTED", "PROCESSING"):
        return None

    request.provider_reference = response.provider_reference or ""
    request.verification_status = response.outcome
    request.failure_code = response.failure_code or ""
    request.failure_reason = response.failure_reason or ""
    request.match_result = dict(response.match or {})
    request.verified_name = (response.verified_name or "")[:255]
    if response.verified_dob:
        from datetime import date

        try:
            y, m, d = (int(x) for x in response.verified_dob.split("-"))
            request.verified_dob = date(y, m, d)
        except (ValueError, TypeError):
            request.verified_dob = None

    from_status = profile.status

    if response.outcome == ProviderOutcome.VERIFIED:
        request.status = RequestStatus.SUCCESS
        request.completed_at = timezone.now()
        now = timezone.now()
        profile.status = KYCStatus.VERIFIED
        profile.verification_level = KYCLevel.LEVEL_2
        profile.verification_method = _merge_method(
            profile.verification_method, KYCVerificationMethod.PROVIDER
        )
        profile.provider = request.provider
        profile.provider_reference = request.provider_reference
        profile.failure_code = ""
        profile.failure_reason = ""
        profile.verified_at = now
        profile.last_checked_at = now
        profile.expires_at = now + timedelta(days=verification_expiry_days())
        profile.save(
            update_fields=[
                "status", "verification_level", "verification_method", "provider",
                "provider_reference", "failure_code", "failure_reason", "verified_at",
                "last_checked_at", "expires_at", "updated_at",
            ]
        )
        request.save(
            update_fields=[
                "status", "completed_at", "provider_reference", "verification_status",
                "failure_code", "failure_reason", "match_result", "verified_name", "verified_dob",
            ]
        )
        record_event(
            profile, request=request, action=KYCEvent.ACTION_VERIFICATION_SUCCESS,
            from_status=from_status, to_status=KYCStatus.VERIFIED,
            provider=request.provider, provider_reference=response.provider_reference or "",
            actor=actor,
            actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
            ip_address=ip_address,
            metadata={"level": KYCLevel.LEVEL_2, "match": request.match_result},
        )
    elif response.outcome == ProviderOutcome.REJECTED:
        request.status = RequestStatus.REJECTED
        request.completed_at = timezone.now()
        terminal = KYCStatus.REJECTED
        if profile.can_transition(terminal):
            profile.status = terminal
            profile.failure_code = response.failure_code or "IDENTITY_MISMATCH"
            profile.failure_reason = response.failure_reason or "Identity verification failed."
            profile.last_checked_at = timezone.now()
            profile.save(
                update_fields=["status", "failure_code", "failure_reason", "last_checked_at", "updated_at"]
            )
        request.save(
            update_fields=[
                "status", "completed_at", "provider_reference", "verification_status",
                "failure_code", "failure_reason", "match_result", "verified_name", "verified_dob",
            ]
        )
        record_event(
            profile, request=request, action=KYCEvent.ACTION_VERIFICATION_FAILED,
            from_status=from_status, to_status=profile.status,
            provider=request.provider, provider_reference=response.provider_reference or "",
            failure_code=response.failure_code or "IDENTITY_MISMATCH",
            actor=actor,
            actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
            ip_address=ip_address,
            metadata={"match": request.match_result},
        )
    elif response.outcome == ProviderOutcome.PENDING:
        request.status = RequestStatus.PROCESSING
        profile.status = KYCStatus.PENDING
        profile.last_checked_at = timezone.now()
        profile.save(update_fields=["status", "last_checked_at", "updated_at"])
        request.save(update_fields=["status", "provider_reference", "verification_status"])
    else:
        _mark_provider_error(
            request, profile,
            failure_code=response.failure_code or "PROVIDER_ERROR",
            reason=response.failure_reason or "Provider reported an error.",
            actor=actor, ip_address=ip_address,
        )
    return request


def _mark_provider_error(request, profile, *, failure_code, reason, actor=None, ip_address=None):
    """A provider outage/exception is NEVER an identity rejection."""
    from_status = profile.status
    request.status = RequestStatus.PROVIDER_ERROR
    request.failure_code = failure_code
    request.failure_reason = reason
    request.save(update_fields=["status", "failure_code", "failure_reason"])
    if profile.can_transition(KYCStatus.PROVIDER_ERROR):
        profile.status = KYCStatus.PROVIDER_ERROR
        profile.failure_code = failure_code
        profile.failure_reason = reason
        profile.last_checked_at = timezone.now()
        profile.save(update_fields=["status", "failure_code", "failure_reason", "last_checked_at", "updated_at"])
    record_event(
        profile, request=request, action=KYCEvent.ACTION_PROVIDER_ERROR,
        from_status=from_status, to_status=profile.status,
        provider=request.provider, failure_code=failure_code,
        actor=actor,
        actor_type=KYCEvent.ACTOR_HUMAN if actor is not None else KYCEvent.ACTOR_SYSTEM,
        ip_address=ip_address,
        metadata={"reason": reason},
    )


# --------------------------------------------------------------------------- #
# Manual review (authorised staff only — fully audited)
# --------------------------------------------------------------------------- #

def manual_review(
    *,
    member,
    decision,
    reason="",
    actor=None,
    ip_address=None,
) -> dict:
    """Manual reviewer action: approve / reject / request_update.

    Grants the legacy staff sign-off path explicit, audited status transitions.
    ``reason`` is mandatory so every human decision on identity is explainable.
    """
    if decision not in {"approve", "reject", "request_update"}:
        raise KYCError("Decision must be one of: approve, reject, request_update.")
    if not reason.strip():
        raise KYCError("A reason is required for manual KYC review.")

    profile = get_or_create_profile(member)
    from_status = profile.status

    with transaction.atomic():
        if decision == "approve":
            if not profile.can_transition(KYCStatus.VERIFIED):
                raise KYCError(f"Cannot approve KYC from state {profile.status}.")
            profile.status = KYCStatus.VERIFIED
            profile.verification_level = _higher_level(profile.verification_level, KYCLevel.LEVEL_1)
            profile.verification_method = _merge_method(profile.verification_method, KYCVerificationMethod.MANUAL_REVIEW)
            profile.failure_code = ""
            profile.failure_reason = ""
            profile.verified_at = timezone.now()
            profile.last_checked_at = timezone.now()
            if not profile.expires_at:
                profile.expires_at = timezone.now() + timedelta(days=verification_expiry_days())
            profile.save(
                update_fields=[
                    "status", "verification_level", "verification_method", "failure_code",
                    "failure_reason", "verified_at", "last_checked_at", "expires_at", "updated_at",
                ]
            )
            action = KYCEvent.ACTION_MANUAL_APPROVE
        elif decision == "reject":
            if not profile.can_transition(KYCStatus.REJECTED):
                raise KYCError(f"Cannot reject KYC from state {profile.status}.")
            profile.status = KYCStatus.REJECTED
            profile.failure_code = "REVIEWER_REJECTION"
            profile.failure_reason = reason
            profile.last_checked_at = timezone.now()
            profile.save(
                update_fields=["status", "failure_code", "failure_reason", "last_checked_at", "updated_at"]
            )
            action = KYCEvent.ACTION_MANUAL_REJECT
        else:  # request_update
            if not profile.can_transition(KYCStatus.REQUIRES_UPDATE):
                raise KYCError(f"Cannot request update from state {profile.status}.")
            profile.status = KYCStatus.REQUIRES_UPDATE
            profile.failure_code = "REVIEWER_REQUESTED_UPDATE"
            profile.failure_reason = reason
            profile.last_checked_at = timezone.now()
            profile.save(
                update_fields=["status", "failure_code", "failure_reason", "last_checked_at", "updated_at"]
            )
            action = KYCEvent.ACTION_REQUIRES_UPDATE

        record_event(
            profile,
            action=action,
            from_status=from_status,
            to_status=profile.status,
            actor=actor,
            actor_type=KYCEvent.ACTOR_HUMAN,
            ip_address=ip_address,
            metadata={"reason": reason, "decision": decision},
        )
    return {"profile": profile}


def _higher_level(current, new):
    if KYCLevel.at_least(current, new):
        return current
    return new


# --------------------------------------------------------------------------- #
# Admin dashboard helpers
# --------------------------------------------------------------------------- #

def dashboard_summary() -> dict:
    from django.db.models import Count

    rows = KYCProfile.objects.values("status").annotate(total=Count("status"))
    counts = {row["status"]: row["total"] for row in rows}
    return {
        "verified": counts.get(KYCStatus.VERIFIED, 0),
        "pending": counts.get(KYCStatus.PENDING, 0),
        "in_review": counts.get(KYCStatus.IN_REVIEW, 0),
        "rejected": counts.get(KYCStatus.REJECTED, 0),
        "expired": counts.get(KYCStatus.EXPIRED, 0),
        "requires_update": counts.get(KYCStatus.REQUIRES_UPDATE, 0),
        "provider_error": counts.get(KYCStatus.PROVIDER_ERROR, 0),
        "not_started": counts.get(KYCStatus.NOT_STARTED, 0),
        "total": sum(counts.values()) or 0,
    }


def admin_profiles(*, status=None, level=None, group_id=None, search=None, verified_from=None, verified_to=None):
    """Filtered profile queryset for the KYC admin dashboard."""
    qs = KYCProfile.objects.select_related("member").prefetch_related(
        "member__group_memberships"
    ).order_by("-updated_at")
    if status:
        qs = qs.filter(status=status)
    if level:
        qs = qs.filter(verification_level=level)
    if group_id:
        qs = qs.filter(member__group_memberships__group_id=group_id)
    if search:
        qs = qs.filter(
            member__first_name__icontains=search
        ) | qs.filter(member__last_name__icontains=search) | qs.filter(
            member__membership_number__icontains=search
        )
    if verified_from:
        qs = qs.filter(verified_at__date__gte=verified_from)
    if verified_to:
        qs = qs.filter(verified_at__date__lte=verified_to)
    return qs.prefetch_related("requests").distinct()