"""Machine-readable error codes for the governance engine."""


class ApprovalError(Exception):
    """Raised by governance workflow or policy services.

    Carries a stable ``code`` for API consumers and a human ``message`` for
    the end user.  Codes intentionally mirror the :data:`payments.errors`
    naming style.
    """

    # Validation / policy
    INVALID_AMOUNT = "INVALID_AMOUNT"
    INSUFFICIENT_AVAILABLE_BALANCE = "INSUFFICIENT_AVAILABLE_BALANCE"
    WITHDRAWAL_LIMIT_EXCEEDED = "WITHDRAWAL_LIMIT_EXCEEDED"
    MINIMUM_RETAINED_BALANCE_VIOLATION = "MINIMUM_RETAINED_BALANCE_VIOLATION"
    WITHDRAWAL_FREQUENCY_EXCEEDED = "WITHDRAWAL_FREQUENCY_EXCEEDED"
    MEMBER_NOT_ACTIVE = "MEMBER_NOT_ACTIVE"
    MEMBER_NOT_IN_GROUP = "MEMBER_NOT_IN_GROUP"
    KYC_REQUIRED = "KYC_REQUIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    POLICY_FAILED = "POLICY_FAILED"

    # Approval workflow
    UNAUTHORIZED_APPROVAL = "UNAUTHORIZED_APPROVAL"
    SELF_APPROVAL_NOT_ALLOWED = "SELF_APPROVAL_NOT_ALLOWED"
    DUPLICATE_APPROVAL = "DUPLICATE_APPROVAL"
    REQUEST_ALREADY_PROCESSED = "REQUEST_ALREADY_PROCESSED"
    REQUEST_EXPIRED = "REQUEST_EXPIRED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"

    # Payment execution
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"

    def __init__(self, code, message=""):
        self.code = code
        self.message = message or code
        super().__init__(self.message)
