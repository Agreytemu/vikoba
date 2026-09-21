"""Stable, machine-readable payment error codes.

Payment exceptions must never leak raw provider messages to clients. Every
failure surfaced to the API carries a stable ``code`` plus a generic, safe
message; the provider detail stays in server logs only.
"""


class PaymentError(Exception):
    PAYMENT_INITIATION_FAILED = "PAYMENT_INITIATION_FAILED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_NOT_FOUND = "PAYMENT_NOT_FOUND"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    INVALID_PROVIDER_REFERENCE = "INVALID_PROVIDER_REFERENCE"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    WEBHOOK_INVALID = "WEBHOOK_INVALID"
    WEBHOOK_ALREADY_PROCESSED = "WEBHOOK_ALREADY_PROCESSED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    INVALID_REQUEST = "INVALID_REQUEST"

    def __init__(self, *, code, message="", detail=None):
        message = message or code
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def is_provider_timeout(exc) -> bool:
    """True when a provider exception means 'request outcome is unknown' — a
    network timeout or an unreachable provider. The payment must stay PENDING
    (not FAILED) until its status is verified, otherwise a retry could charge
    the member twice."""
    return getattr(exc, "code", "") in ("timeout", "provider_unreachable")