from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from accounts.models import SavingsAccount
from members.models import Member


def generate_loan_number():
    year = timezone.now().year

    with transaction.atomic():
        last_loan = (
            LoanAccount.objects
            .select_for_update()
            .filter(loan_number__startswith=f"LN-{year}")
            .order_by("-id")
            .first()
        )

        last_seq = int(last_loan.loan_number.split("-")
                       [-1]) if last_loan else 0
        next_seq = last_seq + 1

        return f"LN-{year}-{next_seq:05d}"


def generate_application_number():
    year = timezone.now().year

    with transaction.atomic():
        last_application = (
            LoanApplication.objects
            .select_for_update()
            .filter(application_number__startswith=f"LA-{year}")
            .order_by("-id")
            .first()
        )

        last_seq = (
            int(last_application.application_number.split("-")[-1])
            if last_application else 0
        )
        next_seq = last_seq + 1
        return f"LA-{year}-{next_seq:05d}"


# Loan products
class LoanProduct(models.Model):
    """
     LoanProduct - defines loan rules
    """
    REDUCING = "reducing"
    FLAT = "flat"

    INTEREST_TYPE_CHOICES = [
        (REDUCING, "Reducing Balance"),
        (FLAT, "Flat Rate"),
    ]

    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    repayment_period_months = models.PositiveIntegerField(default=12)
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.00"))
    interest_type = models.CharField(
        max_length=20,
        choices=INTEREST_TYPE_CHOICES,
        default=REDUCING,
    )

    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_term_months = models.PositiveIntegerField()

    requires_guarantors = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LoanApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        DISBURSED = "disbursed", "Disbursed"

    class SecurityType(models.TextChoices):
        SELF_GUARANTEE = "self_guarantee", "Self Guarantee"
        GUARANTORS = "guarantors", "Guarantors"
        COLLATERAL = "collateral", "Collateral"
        MIXED = "mixed", "Mixed"

    application_number = models.CharField(max_length=20, unique=True, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="loan_applications",
    )
    loan_type = models.ForeignKey(
        LoanProduct,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final amount approved at the approval step. May differ from the requested amount.",
    )
    group = models.ForeignKey(
        "groups.VikobaGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_applications",
        help_text="Group this application belongs to. Inferred at submission and used for group lending policy.",
    )
    purpose = models.TextField()
    repayment_period_months = models.PositiveIntegerField()

    employer = models.CharField(max_length=255, blank=True)
    payroll_number = models.CharField(max_length=100, blank=True)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    security_type = models.CharField(
        max_length=30,
        choices=SecurityType.choices,
        default=SecurityType.SELF_GUARANTEE,
    )
    collateral_description = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_loan_applications",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_loan_applications",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_loan_applications",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_loan_applications",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rejected_loan_applications",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_loan_applications",
    )
    disbursed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="disbursed_loan_applications",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)

    approval_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    disbursement_notes = models.TextField(blank=True)
    eligibility_warnings = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.application_number

    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = generate_application_number()
        super().save(*args, **kwargs)

    def can_edit(self):
        return self.status == self.Status.DRAFT

    def submit(self, user, warnings=None):
        if self.status != self.Status.DRAFT:
            raise ValueError("Only draft applications can be submitted.")

        self.status = self.Status.SUBMITTED
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.eligibility_warnings = warnings or self.eligibility_warnings
        self.save(update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "eligibility_warnings",
        ])

    def start_review(self, user):
        if self.status != self.Status.SUBMITTED:
            raise ValueError("Only submitted applications can be moved to under review.")

        self.status = self.Status.UNDER_REVIEW
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    def approve(self, user, notes=""):
        if self.status != self.Status.UNDER_REVIEW:
            raise ValueError("Only applications under review can be approved.")

        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.approval_notes = notes
        self.save(update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approval_notes",
        ])

    def reject(self, user, reason):
        if self.status != self.Status.UNDER_REVIEW:
            raise ValueError("Only applications under review can be rejected.")
        if not reason:
            raise ValueError("Rejection reason is required.")

        self.status = self.Status.REJECTED
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
        ])

    def cancel(self, user=None, reason=""):
        if self.status not in {
            self.Status.DRAFT,
            self.Status.SUBMITTED,
            self.Status.UNDER_REVIEW,
        }:
            raise ValueError("Only draft, submitted or under-review applications can be cancelled.")

        self.status = self.Status.CANCELLED
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.rejection_reason = reason or self.rejection_reason
        self.save(update_fields=[
            "status",
            "cancelled_by",
            "cancelled_at",
            "rejection_reason",
        ])


def loan_document_upload_path(instance, filename):
    application_number = instance.application.application_number or "draft"
    return f"loan-applications/{application_number}/{filename}"


class LoanApplicationGuarantor(models.Model):
    application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name="guarantors",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="guaranteed_loan_applications",
    )
    guaranteed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("application", "member")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.application.application_number} - {self.member.membership_number}"


class LoanApplicationDocument(models.Model):
    application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to=loan_document_upload_path)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_loan_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.application.application_number} - {self.document_type}"

# Loan Account


class LoanAccount(models.Model):
    """
    LoanAccount has the actual loan
    """
    PENDING = "pending"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    CLOSED = "closed"
    DEFAULTED = "defaulted"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (DISBURSED, "Disbursed"),
        (CLOSED, "Closed"),
        (DEFAULTED, "Defaulted"),
    ]

    loan_number = models.CharField(max_length=20, unique=True)

    member = models.ForeignKey(Member, on_delete=models.PROTECT)
    product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    application = models.OneToOneField(
        LoanApplication,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loan_account",
    )

    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    interest_type = models.CharField(
        max_length=20,
        choices=LoanProduct.INTEREST_TYPE_CHOICES,
        default=LoanProduct.REDUCING,
    )
    penalty_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monthly penalty rate (%) applied to overdue installments.",
    )

    term_months = models.PositiveIntegerField()

    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    outstanding_principal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    outstanding_interest = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    outstanding_penalty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Accumulated penalty charges not yet paid.",
    )

    closed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_loans",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.loan_number

    def save(self, *args, **kwargs):
        if not self.loan_number:
            self.loan_number = generate_loan_number()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status in (self.APPROVED, self.DISBURSED)

    @property
    def total_outstanding(self):
        from .calculations import authoritative_balance
        return authoritative_balance(
            outstanding_principal=self.outstanding_principal,
            outstanding_interest=self.outstanding_interest,
            outstanding_penalty=self.outstanding_penalty,
        )

    def complete(self, user=None):
        """Close the loan once every obligation has been settled."""
        if self.outstanding_principal > 0 or self.outstanding_interest > 0 or self.outstanding_penalty > 0:
            raise ValueError("Cannot close a loan with outstanding obligations.")
        self.status = self.CLOSED
        self.closed_at = timezone.now()
        self.save(update_fields=["status", "closed_at"])


# Loan Schedule
class LoanSchedule(models.Model):
    """
    LoanSchedule contains the expected installments/payments, not actual payments.
    """
    loan = models.ForeignKey(
        LoanAccount,
        on_delete=models.CASCADE,
        related_name="schedule",
    )

    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()

    principal_due = models.DecimalField(max_digits=12, decimal_places=2)
    interest_due = models.DecimalField(max_digits=12, decimal_places=2)
    total_due = models.DecimalField(max_digits=12, decimal_places=2)
    partially_paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative amount already paid toward this installment without settling it.",
    )

    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paid_loan_installments",
    )
    payment_transaction = models.OneToOneField(
        "LoanTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paid_installment",
    )

    class Meta:
        unique_together = ("loan", "installment_number")

    def __str__(self):
        return f"{self.loan.loan_number} - Installment {self.installment_number}"

    @property
    def outstanding_due(self):
        from .calculations import _money
        return _money(self.total_due - self.partially_paid_amount)

    class Status:
        PAID = "PAID"
        PARTIALLY_PAID = "PARTIALLY_PAID"
        OVERDUE = "OVERDUE"
        DUE = "DUE"
        UPCOMING = "UPCOMING"

    @property
    def status(self):
        from django.utils import timezone as _tz
        today = _tz.now().date()
        if self.is_paid:
            return self.Status.PAID
        if self.partially_paid_amount and self.partially_paid_amount > 0:
            return self.Status.PARTIALLY_PAID
        if self.due_date < today:
            return self.Status.OVERDUE
        if self.due_date == today:
            return self.Status.DUE
        return self.Status.UPCOMING

# Loan Transactions


class LoanTransaction(models.Model):
    """
    LoadTransactions contains loan disbursements & repayments transactions
    """
    DISBURSEMENT = "disbursement"
    REPAYMENT = "repayment"
    INTEREST_POSTING = "interest"
    REVERSAL = "reversal"

    TRANSACTION_TYPE_CHOICES = [
        (DISBURSEMENT, "Disbursement"),
        (REPAYMENT, "Repayment"),
        (INTEREST_POSTING, "Interest Posting"),
        (REVERSAL, "Reversal"),
    ]

    loan = models.ForeignKey(
        LoanAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50, unique=True)

    narration = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class LoanPenalty(models.Model):
    """A penalty charge triggered by an overdue loan installment.

    Idempotency per (loan, installment) means re-running overdue processing can
    never double-charge the same installment. Every row is mirrored by an
    engine journal (key ``penalty-{loan_number}-{installment_number}``).
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PAID = "PAID", "Paid"
        WAIVED = "WAIVED", "Waived"

    loan = models.ForeignKey(
        LoanAccount,
        on_delete=models.PROTECT,
        related_name="penalties",
    )
    installment = models.ForeignKey(
        LoanSchedule,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="penalties",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Cumulative payment allocated to this penalty.",
    )
    reason = models.CharField(max_length=200)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    waived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment"],
                condition=models.Q(installment__isnull=False),
                name="unique_loan_installment_penalty",
            )
        ]

    def __str__(self):
        return f"{self.loan.loan_number} - {self.amount}"


class GroupLoanPolicy(models.Model):
    """Per-group lending configuration; ``None`` values inherit product defaults.

    ``effective_{field}`` resolutions live in :mod:`loans.policies`. Approvals
    lock this row (or the group row) before checking group capacity so two
    concurrent approvals cannot exceed the cap (§27/§28 concurrency).
    """

    group = models.OneToOneField(
        "groups.VikobaGroup",
        on_delete=models.CASCADE,
        related_name="loan_policy",
    )
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_term_months = models.PositiveIntegerField(null=True, blank=True)
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    interest_type = models.CharField(
        max_length=20,
        choices=LoanProduct.INTEREST_TYPE_CHOICES,
        null=True,
        blank=True,
    )
    requires_guarantors = models.BooleanField(null=True, blank=True)
    penalty_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monthly penalty rate (%) applied to overdue installments.",
    )
    penalty_grace_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days past due before a penalty is applied.",
    )
    group_capacity_enabled = models.BooleanField(
        default=True,
        help_text="Limit total group lending against aggregate member savings.",
    )
    kyc_level_required = models.CharField(
        max_length=10,
        choices=[("LEVEL_0", "LEVEL_0"), ("LEVEL_1", "LEVEL_1"), ("LEVEL_2", "LEVEL_2")],
        null=True,
        blank=True,
        help_text="KYC verification level the member must satisfy before a loan is "
        "approved/disbursed. None = inherit the platform KYC_REQUIRED_LEVEL default.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_loan_policies",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan policy for {self.group.name}"
