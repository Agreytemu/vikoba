"""KYC profile state machine.

A member's KYC is a status, not a boolean. The profile moves through explicit
states; the transition table below is the single authoritative source used by
:func:`KYCProfile.can_transition`.

Provider failures (PROVIDER_ERROR) are distinct from identity rejection
(REJECTED): a provider going down never marks a member rejected.
"""
from django.utils.translation import gettext_lazy as _


class KYCStatus:
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REQUIRES_UPDATE = "REQUIRES_UPDATE"
    PROVIDER_ERROR = "PROVIDER_ERROR"

    choices = [
        (NOT_STARTED, _("Not started")),
        (PENDING, _("Verification pending")),
        (IN_REVIEW, _("In review")),
        (VERIFIED, _("Verified")),
        (REJECTED, _("Rejected")),
        (EXPIRED, _("Expired")),
        (REQUIRES_UPDATE, _("Requires update")),
        (PROVIDER_ERROR, _("Provider error")),
    ]


class KYCLevel:
    """Verification levels (ordinal; LEVEL_2 implies LEVEL_1)."""

    LEVEL_0 = "LEVEL_0"  # unverified
    LEVEL_1 = "LEVEL_1"  # basic identity verification (manual review / documents)
    LEVEL_2 = "LEVEL_2"  # full identity verification (authoritative national-ID provider)

    choices = [
        (LEVEL_0, _("Unverified")),
        (LEVEL_1, _("Basic verification")),
        (LEVEL_2, _("Full verification")),
    ]

    ORDER = {LEVEL_0: 0, LEVEL_1: 1, LEVEL_2: 2}

    @classmethod
    def at_least(cls, level, required):
        return cls.ORDER.get(level, 0) >= cls.ORDER.get(required, 0)


class KYCVerificationMethod:
    NONE = "NONE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PROVIDER = "PROVIDER"
    BOTH = "BOTH"

    choices = [
        (NONE, _("None")),
        (MANUAL_REVIEW, _("Manual review")),
        (PROVIDER, _("Verification provider")),
        (BOTH, _("Manual review + provider")),
    ]


class RequestStatus:
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    EXPIRED = "EXPIRED"

    choices = [
        (SUBMITTED, _("Submitted")),
        (PROCESSING, _("Processing")),
        (SUCCESS, _("Success")),
        (REJECTED, _("Rejected")),
        (PROVIDER_ERROR, _("Provider error")),
        (EXPIRED, _("Expired")),
    ]


# Allowed profile-state transitions. ``None`` source means "any".
TRANSITIONS = {
    KYCStatus.NOT_STARTED: {
        KYCStatus.PENDING,
        KYCStatus.IN_REVIEW,
        KYCStatus.PROVIDER_ERROR,
        KYCStatus.REJECTED,
        KYCStatus.REQUIRES_UPDATE,
        KYCStatus.VERIFIED,
    },
    KYCStatus.PENDING: {KYCStatus.VERIFIED, KYCStatus.REJECTED, KYCStatus.PROVIDER_ERROR, KYCStatus.IN_REVIEW},
    KYCStatus.IN_REVIEW: {KYCStatus.VERIFIED, KYCStatus.REJECTED, KYCStatus.PROVIDER_ERROR, KYCStatus.REQUIRES_UPDATE},
    KYCStatus.VERIFIED: {KYCStatus.EXPIRED, KYCStatus.REQUIRES_UPDATE, KYCStatus.REJECTED},
    KYCStatus.REJECTED: {KYCStatus.REQUIRES_UPDATE, KYCStatus.VERIFIED, KYCStatus.PENDING},
    KYCStatus.EXPIRED: {KYCStatus.PENDING, KYCStatus.VERIFIED, KYCStatus.REQUIRES_UPDATE},
    KYCStatus.REQUIRES_UPDATE: {KYCStatus.PENDING, KYCStatus.VERIFIED, KYCStatus.REJECTED, KYCStatus.PROVIDER_ERROR},
    KYCStatus.PROVIDER_ERROR: {KYCStatus.PENDING, KYCStatus.VERIFIED, KYCStatus.REJECTED, KYCStatus.REQUIRES_UPDATE},
}


def can_transition(from_status, to_status):
    """True when ``to_status`` is a legal successor of ``from_status``."""
    allowed = TRANSITIONS.get(from_status, set())
    return to_status in allowed


# Providers may advance a profile to VERIFIED / REJECTED / PROVIDER_ERROR only
# from request states that represent an in-flight verification.
REQUEST_PROVIDER_ACTIVE = {RequestStatus.SUBMITTED, RequestStatus.PROCESSING}