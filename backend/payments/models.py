"""Payment transaction model for the Snippe mobile-money gateway.

One row = one logical movement of money through the gateway. The same logical
payment always maps to the same idempotency key, and every terminal provider
reference/event is unique, so double initiations and duplicate webhooks can
never double-post a contribution or repayment.
"""
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def _internal_reference():
    ts = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"VCB-TX-{ts}-{uuid.uuid4().hex[:6].upper()}"


class PaymentTransaction(models.Model):
    """Tracks a payment/disbursement from our side through to settlement."""

    class Type(models.TextChoices):
        CONTRIBUTION = "CONTRIBUTION", "Group contribution"
        LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
        LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan disbursement"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        DEPOSIT = "DEPOSIT", "Wallet deposit"
        SUBSCRIPTION = "SUBSCRIPTION", "Plan subscription"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"
        VOIDED = "VOIDED", "Voided"
        RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED", "Needs reconciliation"

    internal_reference = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        default=_internal_reference,
        db_index=True,
        help_text="Our reference (VCB-TX-...); the idempotency anchor for a retry.",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="payment_transactions",
    )
    group = models.ForeignKey(
        "groups.VikobaGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    phone = models.CharField(max_length=20, blank=True, db_index=True)

    provider = models.CharField(max_length=20, default="snippe")
    provider_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Reference given to us by Snippe for the payment/payout.",
    )
    external_reference = models.CharField(max_length=120, blank=True)

    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    failure_reason = models.CharField(max_length=255, blank=True)

    # Settlement breakdown (only populated once known from Snippe).
    fee = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    idempotency_key = models.CharField(
        max_length=30, unique=True, db_index=True, editable=False
    )

    # Optional link back to the business object being funded.
    contribution = models.ForeignKey(
        "groups.GroupContribution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    loan = models.ForeignKey(
        "loans.LoanAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    installment_number = models.PositiveIntegerField(null=True, blank=True)
    withdrawal = models.ForeignKey(
        "accounts.WithdrawalRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    deposit = models.ForeignKey(
        "accounts.DepositRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )
    subscription = models.ForeignKey(
        "accounts.MemberSubscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_transactions",
    )

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.internal_reference} {self.status}"

    def mark_pending(self, provider_reference, phone="", **metadata):
        updates = {"provider_reference": provider_reference, "metadata": {**self.metadata, **metadata}}
        if phone:
            updates["phone"] = phone
        for field, value in updates.items():
            setattr(self, field, value)
        self.save(update_fields=[*updates.keys(), "updated_at"])
        return self

    def apply_provider_status(self, provider_status, failure_reason=""):
        """Map the provider's raw status onto our ours. Never regresses SUCCESS."""
        if self.status == self.Status.SUCCESS:
            return self
        mapping = {
            "pending": self.Status.PENDING,
            "completed": self.Status.SUCCESS,
            "failed": self.Status.FAILED,
            "voided": self.Status.VOIDED,
            "expired": self.Status.EXPIRED,
        }
        self.status = mapping.get(provider_status, self.Status.PENDING)
        self.failure_reason = failure_reason
        if self.status == self.Status.SUCCESS:
            self.completed_at = timezone.now()
        self.save(update_fields=["status", "failure_reason", "completed_at", "updated_at"])
        return self

    def require_reconciliation(self, reason=""):
        """Move a payment out of the happy path into RECONCILIATION_REQUIRED.

        Never reconstructs or rewrites the amount/history: it only flags the
        record for supervised resolution. Financial effects are never applied."""
        self.status = self.Status.RECONCILIATION_REQUIRED
        self.failure_reason = reason
        self.save(update_fields=["status", "failure_reason", "updated_at"])
        return self


class WebhookEvent(models.Model):
    """Every inbound, signature-verified webhook. Event id is globally unique so
    Snippe's at-least-once delivery can never double-process."""

    event_id = models.CharField(max_length=100, unique=True, db_index=True)
    event_type = models.CharField(max_length=40, db_index=True)
    api_version = models.CharField(max_length=20, blank=True)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} {self.event_id}"


class ReconciliationRecord(models.Model):
    """An audited, never-deleted exception raised while reconciling payments.

    Every financial mismatch (expected vs provider amount/currency, unknown or
    duplicate provider transactions, missing internal records, status
    mismatches) produces one row here. Rows begin OPEN and are only closed by an
    authorised staff resolution that writes an audit event. Nothing is silently
    corrected.
    """

    class IssueType(models.TextChoices):
        AMOUNT_MISMATCH = "AMOUNT_MISMATCH", "Amount discrepancy"
        CURRENCY_MISMATCH = "CURRENCY_MISMATCH", "Currency mismatch"
        UNKNOWN_PROVIDER_TRANSACTION = "UNKNOWN_PROVIDER_TRANSACTION", "Unknown provider transaction"
        DUPLICATE_PROVIDER_TRANSACTION = "DUPLICATE_PROVIDER_TRANSACTION", "Duplicate provider transaction"
        MISSING_INTERNAL_TRANSACTION = "MISSING_INTERNAL_TRANSACTION", "Missing internal transaction"
        MISSING_WEBHOOK = "MISSING_WEBHOOK", "Missing webhook"
        DELAYED_CONFIRMATION = "DELAYED_CONFIRMATION", "Delayed confirmation"
        STATUS_MISMATCH = "STATUS_MISMATCH", "Status mismatch"
        ALREADY_PROCESSED_EVENT = "ALREADY_PROCESSED_EVENT", "Already processed event"
        PROVIDER_ERROR = "PROVIDER_ERROR", "Provider error"

    class ResolutionStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"

    payment = models.ForeignKey(
        "payments.PaymentTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_records",
        help_text="Null when the provider transaction has no internal payment yet.",
    )
    provider = models.CharField(max_length=20, default="snippe")
    provider_reference = models.CharField(max_length=100, blank=True, db_index=True)
    internal_reference = models.CharField(max_length=40, blank=True, db_index=True)
    event_id = models.CharField(max_length=100, blank=True)

    issue_type = models.CharField(max_length=40, choices=IssueType.choices, db_index=True)

    expected_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    expected_currency = models.CharField(max_length=3, blank=True)
    actual_currency = models.CharField(max_length=3, blank=True)
    expected_status = models.CharField(max_length=30, blank=True)
    actual_status = models.CharField(max_length=30, blank=True)

    resolution_status = models.CharField(
        max_length=12, choices=ResolutionStatus.choices, default=ResolutionStatus.OPEN, db_index=True
    )
    notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciled_payment_records",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_reference", "issue_type"],
                name="unique_reconciliation_provider_ref_issue",
            )
        ]

    def __str__(self):
        return f"{self.issue_type} {self.provider_reference or self.internal_reference}"