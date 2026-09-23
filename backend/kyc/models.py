"""KYC domain models.

Three concerns, kept separate (retention-friendly):
- ``KYCProfile`` — the member's *current* verification state (status, level,
  method, latest provider link, expiry). One per member.
- ``KYCVerificationRequest`` — one idempotent verification flow; doubles as the
  stored structured *result* of that attempt (provider, reference, outcome,
  match flags, failure code, attempt accounting).
- ``KYCEvent`` — the append-only audit / observability trail.

Sensitive minimisation: the member's full national ID is owned by
``members.Member``; the KYC domain stores only match *flags* and masked/provider
references, never raw identity documents or full raw provider payloads.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from kyc.statuses import (
    KYCLevel,
    KYCStatus,
    KYCVerificationMethod,
    RequestStatus,
    can_transition,
)


def new_request_ref():
    return f"KYC-{uuid.uuid4().hex[:10].upper()}"


class KYCProfile(models.Model):
    """The member's current, authoritative KYC state (one per member)."""

    member = models.OneToOneField(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="kyc_profile",
        primary_key=True,
    )

    status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.NOT_STARTED,
        db_index=True,
        help_text="Current KYC state (NOT a frontend-controllable field — only the "
        "backend verification process or an authorised reviewer transitions it).",
    )
    verification_level = models.CharField(
        max_length=10, choices=KYCLevel.choices, default=KYCLevel.LEVEL_0
    )
    verification_method = models.CharField(
        max_length=20, choices=KYCVerificationMethod.choices, default=KYCVerificationMethod.NONE
    )
    provider = models.CharField(max_length=40, blank=True, default="")
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    failure_code = models.CharField(max_length=40, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")

    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="When the current verification stops being valid."
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.member.membership_number} [{self.status}/{self.verification_level}]"

    @property
    def expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def can_transition(self, to_status):
        return can_transition(self.status, to_status)


class KYCVerificationRequest(models.Model):
    """One idempotent verification flow and its stored structured result.

    A member may have at most ONE in-flight request (SUBMITTED/PROCESSING) at a
    time — enforced at the DB level so repeated clicks can never fan out into
    multiple uncontrolled provider calls. ``idempotency_key`` lets a client
    resubmit safely; a succeeded/rejected request is returned as-is.
    """

    profile = models.ForeignKey(
        KYCProfile, on_delete=models.CASCADE, related_name="requests"
    )
    request_ref = models.CharField(max_length=20, unique=True, default=new_request_ref)
    idempotency_key = models.CharField(
        max_length=120, unique=True, null=True, blank=True,
        help_text="Client-supplied key; repeating a submission with the same key "
        "never creates a second provider request.",
    )

    status = models.CharField(
        max_length=20, choices=RequestStatus.choices, default=RequestStatus.SUBMITTED, db_index=True
    )
    attempt_count = models.PositiveSmallIntegerField(default=1)
    max_attempts = models.PositiveSmallIntegerField(default=3)

    # --- Stored structured result (KYC design section 13) ---
    provider = models.CharField(max_length=40, blank=True, default="")
    provider_reference = models.CharField(
        max_length=120, unique=True, null=True, blank=True,
        help_text="Provider-side reference for this attempt (masked in responses).",
    )
    verification_status = models.CharField(max_length=20, blank=True, default="")
    failure_code = models.CharField(max_length=40, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    match_result = models.JSONField(
        default=dict, blank=True,
        help_text='Match flags only, e.g. {"full_name": true, "date_of_birth": true, '
        '"national_id": true}. Never raw identity values.',
    )
    verified_name = models.CharField(max_length=255, blank=True, default="")
    verified_dob = models.DateField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            UniqueConstraint(
                fields=["profile"],
                condition=Q(status__in=["SUBMITTED", "PROCESSING"]),
                name="kyc_request_single_active",
            ),
        ]

    def __str__(self):
        return f"{self.request_ref} [{self.status}]"


class KYCEvent(models.Model):
    """Append-only KYC audit / observability trail. Never edited or deleted."""

    ACTOR_SYSTEM = "SYSTEM"
    ACTOR_HUMAN = "HUMAN"
    ACTOR_CHOICES = ((ACTOR_SYSTEM, "System"), (ACTOR_HUMAN, "Human"))

    # Observability tokens (KYC design section 32). No raw identity values are
    # ever logged — only references, statuses and failure categories.
    ACTION_REQUEST_STARTED = "KYC_REQUEST_STARTED"
    ACTION_PROVIDER_REQUEST = "KYC_PROVIDER_REQUEST"
    ACTION_PROVIDER_RESPONSE = "KYC_PROVIDER_RESPONSE"
    ACTION_VERIFICATION_SUCCESS = "KYC_VERIFICATION_SUCCESS"
    ACTION_VERIFICATION_FAILED = "KYC_VERIFICATION_FAILED"
    ACTION_PROVIDER_ERROR = "KYC_PROVIDER_ERROR"
    ACTION_RETRY = "KYC_RETRY"
    ACTION_STATUS_CHANGED = "KYC_STATUS_CHANGED"
    ACTION_MANUAL_APPROVE = "KYC_MANUAL_APPROVE"
    ACTION_MANUAL_REJECT = "KYC_MANUAL_REJECT"
    ACTION_REQUIRES_UPDATE = "KYC_REQUIRES_UPDATE"
    ACTION_EXPIRED = "KYC_EXPIRED"
    ACTION_SYNCED_FROM_MEMBER = "KYC_SYNCED_FROM_MEMBER"

    profile = models.ForeignKey(
        KYCProfile, on_delete=models.CASCADE, related_name="events"
    )
    request = models.ForeignKey(
        KYCVerificationRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    action = models.CharField(max_length=40, db_index=True)
    status = models.CharField(max_length=20, blank=True, default="")
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20, blank=True, default="")
    provider = models.CharField(max_length=40, blank=True, default="")
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    failure_code = models.CharField(max_length=40, blank=True, default="")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_events",
    )
    actor_type = models.CharField(max_length=10, choices=ACTOR_CHOICES, default=ACTOR_SYSTEM)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["profile", "created_at"])]

    def __str__(self):
        return f"{self.action} on {self.profile_id}"