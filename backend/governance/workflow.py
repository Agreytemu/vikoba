"""Reusable governance workflow (the approval state machine).

The same workflow powers withdrawals, loan applications and any future
governable operation.  Business execution after a decision is delegated to an
executor keyed by ``request_type`` (see :mod:`governance.withdrawals`).

Core rules enforced here:

* Only authorized approvers (matching committee role / staff role within the
  request's group) may act — the backend is authoritative.
* A requester can never approve their own request (segregation of duties).
* One human ``approve`` per request per actor (duplicate approvals blocked).
* Rejected / cancelled / expired / completed / auto-approved requests are
  terminal for human action.
* Every decision — automatic (SYSTEM) or human — is recorded as an
  :class:`~governance.models.ApprovalAction` audit row.
"""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from governance.errors import ApprovalError
from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    Decision,
    RequestType,
    RequiredLevel,
)

SYSTEM_OFFICER_ROLES = frozenset(
    getattr(settings, "GOVERNANCE_OFFICER_ROLES", ("AD", "MA", "OP", "FI", "AC"))
)
COMMITTEE_ROLES = ("CHAIRPERSON", "SECRETARY", "TREASURER")


# ---------------------------------------------------------------------------
# Request creation
# ---------------------------------------------------------------------------

def create_request(
    *,
    group,
    request_type,
    resource,
    requester,
    amount,
    currency="TZS",
    required_level=RequiredLevel.MANUAL,
    required_role="",
    review_roles=None,
    decision=None,
    decision_reason="",
    rules_passed=None,
    policy_version="",
    metadata=None,
    idempotency_key=None,
    expires_at=None,
):
    """Create an ApprovalRequest and record the ``submit`` action.

    ``review_roles`` (list of role names in order) builds the ApprovalSteps;
    single-level review is a one-entry list. Returns the request."""
    if idempotency_key:
        existing = ApprovalRequest.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    request = ApprovalRequest.objects.create(
        group=group,
        request_type=request_type,
        content_type=None if resource is None else _ctype(resource),
        object_id=None if resource is None else resource.pk,
        resource_description=_describe(resource),
        requester=requester,
        amount=amount,
        currency=currency,
        required_level=required_level,
        required_role=required_role or (review_roles[0] if review_roles else ""),
        status=ApprovalStatus.PENDING,
        decision=decision if decision else None,
        decision_reason=decision_reason or "",
        rules_passed=rules_passed or [],
        policy_version=policy_version or "",
        expires_at=expires_at,
        idempotency_key=idempotency_key or None,
        metadata=metadata or {},
    )
    record_action(
        request=request,
        action=ApprovalAction.ACTION_SUBMIT,
        from_status="",
        to_status=ApprovalStatus.PENDING,
        actor=requester,
        decision=decision,
        reason=decision_reason,
    )
    if review_roles:
        add_steps(request, review_roles)
    return request


def add_steps(request, roles):
    ApprovalStep.objects.bulk_create(
        [
            ApprovalStep(
                request=request,
                level=index,
                role=role_name,
                required_human=role_name not in ("SYSTEM", "AUTO"),
            )
            for index, role_name in enumerate(roles, start=1)
        ]
    )


def record_action(
    *,
    request,
    action,
    from_status,
    to_status,
    actor=None,
    actor_type=ApprovalAction.ACTOR_HUMAN,
    decision=None,
    reason="",
    ip=None,
):
    return ApprovalAction.objects.create(
        request=request,
        actor=actor,
        actor_type=actor_type,
        action=action,
        decision=decision,
        reason=reason or "",
        from_status=from_status or "",
        to_status=to_status or "",
        ip_address=ip,
    )


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def satisfies_role(user, group, role) -> bool:
    """True if ``user`` may act in ``role`` for ``group``.

    Platform officers (GOVERNANCE_OFFICER_ROLES) supersede committee roles —
    they may act for any group (matching existing staff-wide visibility).
    Committee roles require an active membership in that group only."""
    role = role or ""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or (getattr(user, "role", None) in SYSTEM_OFFICER_ROLES):
        return True
    if role not in COMMITTEE_ROLES:
        from users.permissions import has_role

        return has_role(user, {role})
    if group is None:
        return False
    from groups.models import GroupMembership

    return GroupMembership.objects.filter(
        group=group,
        member__user=user,
        role=role,
        is_active=True,
    ).exists()


def can_review(user, request) -> bool:
    """Can ``user`` approve this request right now, ignoring SoD (handled in
    :func:`approve`)?"""
    role = request.required_role
    if not role:
        return user.is_superuser or (getattr(user, "role", None) in SYSTEM_OFFICER_ROLES)
    return satisfies_role(user, request.group, role)


def next_step_for_user(user, request):
    """The first pending step the user is authorized for, else None."""
    steps = request.steps.filter(status=ApprovalStep.Status.PENDING).order_by("level")
    for step in steps:
        if satisfies_role(user, request.group, step.role):
            return step
    return None


# ---------------------------------------------------------------------------
# Approver actions
# ---------------------------------------------------------------------------

def _guard_pending(request):
    if request.status in (
        ApprovalStatus.APPROVED,
        ApprovalStatus.AUTO_APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.CANCELLED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.COMPLETED,
        ApprovalStatus.FAILED,
    ):
        raise ApprovalError(
            ApprovalError.REQUEST_ALREADY_PROCESSED,
            "This request has already been processed.",
        )
    if request.is_expired:
        raise ApprovalError(
            ApprovalError.REQUEST_EXPIRED,
            "This request has expired.",
        )
    if request.status != ApprovalStatus.PENDING:
        raise ApprovalError(
            ApprovalError.INVALID_STATE_TRANSITION,
            f"Cannot act on a request in state {request.status}.",
        )


def _expire_guard(request):
    """Handle an expired request OUTSIDE any caller rollback scope, so the
    EXPIRED state transition is committed (expiry releases reservations)."""
    if request.is_expired and request.status == ApprovalStatus.PENDING:
        expire(request)
        raise ApprovalError(
            ApprovalError.REQUEST_EXPIRED,
            "This request has expired.",
        )


def approve(*, request, user, reason="", ip=None):
    """Human approval. Applies SoD, authorization, dedupe and state guards,
    then advances the workflow and executes the domain action when complete."""
    _expire_guard(request)
    with transaction.atomic():
        request = (
            ApprovalRequest.objects.select_for_update()
            .select_related("requester", "group")
            .prefetch_related("steps")
            .get(pk=request.pk)
        )
        _guard_pending(request)

        if request.requester_id and request.requester_id == user.pk:
            raise ApprovalError(
                ApprovalError.SELF_APPROVAL_NOT_ALLOWED,
                "You cannot approve your own request.",
            )
        if ApprovalAction.objects.filter(
            request=request,
            actor=user,
            actor_type=ApprovalAction.ACTOR_HUMAN,
            action=ApprovalAction.ACTION_APPROVE,
        ).exists():
            raise ApprovalError(
                ApprovalError.DUPLICATE_APPROVAL,
                "You have already approved this request.",
            )

        step = next_step_for_user(user, request)
        if step is None and not can_review(user, request):
            raise ApprovalError(
                ApprovalError.UNAUTHORIZED_APPROVAL,
                "You are not authorized to approve this request.",
            )

        if step is not None:
            step.status = ApprovalStep.Status.APPROVED
            step.approved_by = user
            step.approved_at = timezone.now()
            step.reason = reason or ""
            step.save(update_fields=["status", "approved_by", "approved_at", "reason"])

        remaining = request.steps.filter(status=ApprovalStep.Status.PENDING).exists()
        if remaining:
            record_action(
                request=request,
                action=ApprovalAction.ACTION_APPROVE,
                from_status=ApprovalStatus.PENDING,
                to_status=ApprovalStatus.PENDING,
                actor=user,
                actor_type=ApprovalAction.ACTOR_HUMAN,
                decision=Decision.MANUAL_REVIEW,
                reason=reason,
                ip=ip,
            )
            request.refresh_from_db()
            return request

        request.status = ApprovalStatus.APPROVED
        request.save(update_fields=["status", "updated_at"])
        record_action(
            request=request,
            action=ApprovalAction.ACTION_APPROVE,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.APPROVED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_HUMAN,
            decision=Decision.MANUAL_REVIEW,
            reason=reason,
            ip=ip,
        )
        _execute(request)
        request.refresh_from_db()
        return request


def reject(*, request, user, reason="", ip=None):
    """Human rejection. The requester who rejects is a reviewer; self-rejection
    is allowed for the requester only via :func:`cancel`."""
    _expire_guard(request)
    with transaction.atomic():
        request = (
            ApprovalRequest.objects.select_for_update()
            .select_related("requester", "group")
            .get(pk=request.pk)
        )
        _guard_pending(request)

        authorizer = user.is_superuser or (getattr(user, "role", None) in SYSTEM_OFFICER_ROLES)
        if authorizer or request.requester_id == user.pk:
            pass
        elif request.steps.filter(status=ApprovalStep.Status.PENDING).exists():
            ok = any(satisfies_role(user, request.group, s.role) for s in request.steps.all())
            if not ok:
                raise ApprovalError(ApprovalError.UNAUTHORIZED_APPROVAL, "You are not authorized to reject this request.")
        else:
            raise ApprovalError(ApprovalError.UNAUTHORIZED_APPROVAL, "You are not authorized to reject this request.")

        request.status = ApprovalStatus.REJECTED
        request.decision = Decision.REJECTED
        request.decision_reason = reason or request.decision_reason
        request.save(update_fields=["status", "decision", "decision_reason", "updated_at"])
        request.steps.exclude(status=ApprovalStep.Status.APPROVED).update(status=ApprovalStep.Status.REJECTED)
        record_action(
            request=request,
            action=ApprovalAction.ACTION_REJECT,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.REJECTED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_HUMAN,
            decision=Decision.REJECTED,
            reason=reason,
            ip=ip,
        )
        _execute(request)
        request.refresh_from_db()
        return request


def cancel(*, request, user, reason="", ip=None):
    """Cancel a pending request — permitted for the requester, a platform
    officer, or an authorized reviewer of the request."""
    _expire_guard(request)
    with transaction.atomic():
        request = (
            ApprovalRequest.objects.select_for_update()
            .select_related("requester", "group")
            .get(pk=request.pk)
        )
        _guard_pending(request)

        authorized = (
            user.is_superuser
            or (getattr(user, "role", None) in SYSTEM_OFFICER_ROLES)
            or request.requester_id == user.pk
            or can_review(user, request)
        )
        if not authorized:
            raise ApprovalError(ApprovalError.UNAUTHORIZED_APPROVAL, "You are not authorized to cancel this request.")

        request.status = ApprovalStatus.CANCELLED
        request.save(update_fields=["status", "updated_at"])
        request.steps.filter(status=ApprovalStep.Status.PENDING).update(status=ApprovalStep.Status.SKIPPED)
        record_action(
            request=request,
            action=ApprovalAction.ACTION_CANCEL,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.CANCELLED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_HUMAN,
            reason=reason,
            ip=ip,
        )
        _execute(request)
        request.refresh_from_db()
        return request


def auto_approve(*, request, user=None, reason="", ip=None):
    """Record an automatic system decision (AUTO_APPROVED) and execute."""
    with transaction.atomic():
        request = (
            ApprovalRequest.objects.select_for_update().select_related("requester", "group").get(pk=request.pk)
        )
        _guard_pending(request)
        request.status = ApprovalStatus.APPROVED
        request.decision = Decision.AUTO_APPROVED
        request.save(update_fields=["status", "decision", "updated_at"])
        record_action(
            request=request,
            action=ApprovalAction.ACTION_AUTO_APPROVE,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.APPROVED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            decision=Decision.AUTO_APPROVED,
            reason=reason or "Withdrawal satisfied configured group policy.",
            ip=ip,
        )
        _execute(request)
        request.refresh_from_db()
        return request


def expire(request):
    """Internal: flip an expired request to EXPIRED and release its side
    effects."""
    with transaction.atomic():
        request = ApprovalRequest.objects.select_for_update().get(pk=request.pk)
        if request.is_expired and request.status == ApprovalStatus.PENDING:
            request.status = ApprovalStatus.EXPIRED
            request.save(update_fields=["status", "updated_at"])
            request.steps.filter(status=ApprovalStep.Status.PENDING).update(status=ApprovalStep.Status.SKIPPED)
            record_action(
                request=request,
                action=ApprovalAction.ACTION_EXPIRE,
                from_status=ApprovalStatus.PENDING,
                to_status=ApprovalStatus.EXPIRED,
                actor=None,
                actor_type=ApprovalAction.ACTOR_SYSTEM,
                decision=Decision.MANUAL_REVIEW,
                reason="Approval window elapsed.",
            )
            _execute(request)
        return request


def expire_due_requests(now=None):
    """Expire every PENDING request past its deadline. Returns count."""
    now = now or timezone.now()
    due = list(
        ApprovalRequest.objects.filter(
            status=ApprovalStatus.PENDING,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
    )
    for request in due:
        expire(request)
    return len(due)


def mark_processing(request, *, user=None, reason="", ip=None):
    with transaction.atomic():
        request = ApprovalRequest.objects.select_for_update().get(pk=request.pk)
        if request.status not in (ApprovalStatus.APPROVED,):
            raise ApprovalError(ApprovalError.INVALID_STATE_TRANSITION, "Only approved requests enter processing.")
        request.status = ApprovalStatus.PROCESSING
        request.save(update_fields=["status", "updated_at"])
        record_action(
            request=request,
            action=ApprovalAction.ACTION_MARK_PROCESSING,
            from_status=ApprovalStatus.APPROVED,
            to_status=ApprovalStatus.PROCESSING,
            actor=user,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            reason=reason,
            ip=ip,
        )
        return request


def complete(request, *, user=None, reason="", ip=None):
    with transaction.atomic():
        request = ApprovalRequest.objects.select_for_update().get(pk=request.pk)
        if request.status != ApprovalStatus.PROCESSING:
            raise ApprovalError(ApprovalError.INVALID_STATE_TRANSITION, "Only processing requests can complete.")
        request.status = ApprovalStatus.COMPLETED
        request.save(update_fields=["status", "updated_at"])
        record_action(
            request=request,
            action=ApprovalAction.ACTION_COMPLETE,
            from_status=ApprovalStatus.PROCESSING,
            to_status=ApprovalStatus.COMPLETED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            reason=reason,
            ip=ip,
        )
        return request


def fail(request, *, user=None, reason="", ip=None):
    with transaction.atomic():
        request = ApprovalRequest.objects.select_for_update().get(pk=request.pk)
        if request.status not in (ApprovalStatus.PROCESSING, ApprovalStatus.APPROVED):
            raise ApprovalError(ApprovalError.INVALID_STATE_TRANSITION, "Cannot mark this request failed.")
        request.status = ApprovalStatus.FAILED
        request.save(update_fields=["status", "updated_at"])
        record_action(
            request=request,
            action=ApprovalAction.ACTION_FAIL,
            from_status=ApprovalStatus.PROCESSING,
            to_status=ApprovalStatus.FAILED,
            actor=user,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            reason=reason,
            ip=ip,
        )
        return request


# ---------------------------------------------------------------------------
# Executor dispatch
# ---------------------------------------------------------------------------

def _execute(request):
    """Route the now-resolved request to its domain executor.

    Executors live in their domain apps so governance stays generic; today only
    withdrawals have a real executor (loans record decisions via a light
    adapter)."""
    from governance.withdrawals import execute_request

    execute_request(request)


# ---------------------------------------------------------------------------
# Inbox / queries
# ---------------------------------------------------------------------------

def approval_inbox(user, *, request_type=None, statuses=None):
    """Approvals visible to ``user``.

    Platform officers see all groups (staff-wide visibility, consistent with
    the existing system). Committee officers see their own groups; a regular
    member only sees their own requests."""
    statuses = statuses or [ApprovalStatus.PENDING]
    qs = (
        ApprovalRequest.objects.select_related("requester", "group")
        .prefetch_related("steps")
    )
    if not (user.is_superuser or getattr(user, "role", None) in SYSTEM_OFFICER_ROLES):
        member = getattr(user, "member", None)
        if member is None:
            return ApprovalRequest.objects.none()
        from groups.models import GroupMembership

        group_ids = list(
            GroupMembership.objects.filter(
                member=member,
                is_active=True,
                role__in=COMMITTEE_ROLES,
            ).values_list("group_id", flat=True)
        )
        qs = qs.filter(
            models.Q(group_id__in=group_ids)
            | models.Q(requester=user)
        ).distinct()
    if request_type:
        qs = qs.filter(request_type=request_type)
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs


def visible_request(user, request) -> bool:
    """Can ``user`` read/detail this request (group isolation on the read side)?"""
    if user.is_superuser or (getattr(user, "role", None) in SYSTEM_OFFICER_ROLES):
        return True
    if request.requester_id == user.pk:
        return True
    member = getattr(user, "member", None)
    if member is None or request.group_id is None:
        return False
    from groups.models import GroupMembership

    return GroupMembership.objects.filter(
        group_id=request.group_id,
        member=member,
        is_active=True,
        role__in=COMMITTEE_ROLES,
    ).exists()


def _ctype(resource):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(resource)


def _describe(resource):
    if resource is None:
        return ""
    name = getattr(resource, "reference", None) or getattr(resource, "application_number", None) or ""
    return str(name)