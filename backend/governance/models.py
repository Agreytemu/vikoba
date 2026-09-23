"""Reusable VICOBA governance & approval engine.

The engine centralises the approval lifecycle for sensitive financial
operations (withdrawals, loan applications, and future request types) while the
business logic of each domain lives in its own app. See :mod:`governance.workflow`
for the state machine and :mod:`governance.policy` for the deterministic
withdrawal decision policy.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class RequestType(models.TextChoices):
    WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
    LOAN_APPLICATION = "LOAN_APPLICATION", "Loan application"
    DEPOSIT = "DEPOSIT", "Deposit request"
    POLICY_CHANGE = "POLICY_CHANGE", "Group policy change"
    GROUP_EXPENSE = "GROUP_EXPENSE", "Group expense"
    FINANCIAL_ADJUSTMENT = "FINANCIAL_ADJUSTMENT", "Financial adjustment"


class Decision(models.TextChoices):
    AUTO_APPROVED = "AUTO_APPROVED", "Auto approved"
    MANUAL_REVIEW = "MANUAL_REVIEW", "Manual review"
    REJECTED = "REJECTED", "Rejected"


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    AUTO_APPROVED = "AUTO_APPROVED", "Auto approved"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class RequiredLevel(models.TextChoices):
    AUTOMATIC = "AUTO", "Automatic"
    MANUAL = "MANUAL", "Manual review"
    MULTI = "MULTI", "Multi-level review"


class ApprovalRequest(models.Model):
    """One governable financial operation awaiting (or resolved by) an approval
    decision. Created for every sensitive operation; automatic decisions are
    recorded here too so every decision is traceable (§22-§24)."""

    group = models.ForeignKey(
        "groups.VikobaGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests",
    )
    request_type = models.CharField(max_length=30, choices=RequestType.choices)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    resource = GenericForeignKey("content_type", "object_id")
    resource_description = models.CharField(max_length=255, blank=True)

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_approval_requests",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=4, default="TZS")

    required_level = models.CharField(
        max_length=10,
        choices=RequiredLevel.choices,
        default=RequiredLevel.MANUAL,
    )
    required_role = models.CharField(
        max_length=40,
        blank=True,
        help_text="Role required to approve (committee role like TREASURER, or staff role code).",
    )

    status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        null=True,
        blank=True,
    )
    decision_reason = models.TextField(blank=True)
    rules_passed = models.JSONField(default=list, blank=True)
    policy_version = models.CharField(max_length=60, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        help_text="Optional idempotency guard for exactly-once submission.",
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "request_type"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.request_type} {self.pk} [{self.status}]"

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()


class ApprovalStep(models.Model):
    """One approval level of a request. Single-level requests carry one step
    (the manual-review role); multi-level requests carry ordered steps (e.g.
    Treasurer then Chairperson)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SKIPPED = "SKIPPED", "Skipped"

    request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    level = models.PositiveIntegerField(default=1)
    role = models.CharField(max_length=40)
    required_human = models.BooleanField(default=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_approval_steps",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["request", "level"], name="unique_approval_step_level"),
        ]
        ordering = ["level"]

    def __str__(self):
        return f"{self.request} step {self.level} ({self.role})"


class ApprovalAction(models.Model):
    """Append-only audit record of every governance decision — automatic
    (SYSTEM) or human. Never edited or deleted."""

    ACTOR_SYSTEM = "SYSTEM"
    ACTOR_HUMAN = "HUMAN"
    ACTOR_CHOICES = ((ACTOR_SYSTEM, "System"), (ACTOR_HUMAN, "Human"))

    ACTION_SUBMIT = "submit"
    ACTION_AUTO_APPROVE = "auto_approve"
    ACTION_REVIEW_REQUIRED = "review_required"
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_CANCEL = "cancel"
    ACTION_EXPIRE = "expire"
    ACTION_MARK_PROCESSING = "mark_processing"
    ACTION_COMPLETE = "complete"
    ACTION_FAIL = "fail"

    request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="governance_actions",
    )
    actor_type = models.CharField(
        max_length=10,
        choices=ACTOR_CHOICES,
        default=ACTOR_HUMAN,
    )
    action = models.CharField(max_length=30)
    decision = models.CharField(max_length=20, choices=Decision.choices, null=True, blank=True)
    reason = models.TextField(blank=True)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["request", "created_at"])]

    def __str__(self):
        return f"{self.action} {self.request_id} by {self.actor_type}"


class GroupWithdrawalPolicy(models.Model):
    """Per-group withdrawal governance configuration.

    ``None`` fields inherit the platform defaults in :data:`governance.policy`
    (mirroring the ``GroupLoanPolicy`` inheritance pattern). Updated only by
    authorized committee officers or platform staff; every update is recorded
    through the audit engine."""

    REVIEWER_ROLE_DEFAULT = "TREASURER"
    REVIEWER_ROLE_CHOICES = (
        ("CHAIRPERSON", "Chairperson"),
        ("SECRETARY", "Secretary"),
        ("TREASURER", "Treasurer"),
    )
    REVIEW_SINGLE = "SINGLE"
    REVIEW_TWO_LEVEL = "TWO_LEVEL"
    REVIEW_LEVEL_CHOICES = (
        (REVIEW_SINGLE, "Single review"),
        (REVIEW_TWO_LEVEL, "Treasurer + Chairperson"),
    )

    group = models.OneToOneField(
        "groups.VikobaGroup",
        on_delete=models.CASCADE,
        related_name="withdrawal_policy",
    )

    auto_approve_limit = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Withdrawals up to this amount are auto-approved; above it goes to manual review. None = unlimited.",
    )
    max_withdrawal_limit = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Hard ceiling per withdrawal. None = no ceiling.",
    )
    min_withdrawal_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Minimum single withdrawal. None = no minimum.",
    )
    weekly_withdrawal_limit = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Maximum total withdrawn by a member per rolling week before manual review.",
    )
    weekly_withdrawal_count = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Maximum number of withdrawals a member can make per rolling week before manual review.",
    )
    monthly_withdrawal_limit = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Maximum total withdrawn by a member per rolling month before manual review.",
    )
    min_retained_ratio = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Fraction of the savings balance that must remain after the withdrawal. None = 0.",
    )
    review_on_outstanding_loan = models.BooleanField(
        default=False,
        help_text="Route to manual review when the member has an outstanding loan.",
    )
    review_on_outstanding_penalty = models.BooleanField(
        default=False,
        help_text="Route to manual review when the member has an unpaid loan penalty.",
    )
    kyc_level_required = models.CharField(
        max_length=10,
        choices=[("LEVEL_0", "LEVEL_0"), ("LEVEL_1", "LEVEL_1"), ("LEVEL_2", "LEVEL_2")],
        null=True,
        blank=True,
        help_text="KYC verification level required before a member may withdraw. "
        "None = inherit the platform KYC_REQUIRED_LEVEL default.",
    )
    review_levels = models.CharField(
        max_length=12,
        choices=REVIEW_LEVEL_CHOICES,
        default=REVIEW_SINGLE,
        help_text="Review levels required for a manual-review withdrawal.",
    )
    reviewer_role = models.CharField(
        max_length=20,
        choices=REVIEWER_ROLE_CHOICES,
        default=REVIEWER_ROLE_DEFAULT,
        help_text="Committee role required for manual approval.",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_withdrawal_policies",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Withdrawal policy for {self.group.name}"