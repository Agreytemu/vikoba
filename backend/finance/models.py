"""Financial core models: chart of accounts, double-entry journal and the
central financial transaction record that feeds the transaction engine.

Money representation:
- Every amount is a ``Decimal`` stored in a ``DecimalField`` (never float/double).
- Zero and negative amounts are rejected at the database level for journal entries.

Ledger rules enforced here (and centrally in ``finance.services.engine``):
- A posted financial transaction must have balanced journal entries.
- Successful financial transactions are never deleted — only reversed.
"""
from django.conf import settings
from django.db import models


class ReferenceCounter(models.Model):
    """Per-prefix, per-day monotonic counter used to allocate human-readable,
    unique and never-reused financial references (e.g. DEP-20260920-000123)."""

    prefix = models.CharField(max_length=8)
    day = models.CharField(max_length=8, help_text="YYYYMMDD")
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prefix", "day"], name="unique_reference_counter_prefix_day"
            )
        ]

    def __str__(self):
        return f"{self.prefix}/{self.day}/{self.last_sequence}"


class FinancialAccount(models.Model):
    """One financial account in the VICOBA chart of accounts.

    Organization-level accounts (SUSPENSE, CLEARING, income/expense...) have
    ``group``/``member``/``savings_account``/``loan_account`` empty. Accounts that
    follow a business object (member savings, group cash, loan receivable) keep a
    link so balances can be scoped and audited.
    """

    class AccountType(models.TextChoices):
        ASSET = "ASSET", "Asset"
        LIABILITY = "LIABILITY", "Liability"
        EQUITY = "EQUITY", "Equity"
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    # Human-readable, unique, stable code (e.g. "1100-CLEARING", "MS-SA00000012").
    account_number = models.CharField(
        max_length=40, unique=True, editable=False, db_index=True
    )
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=10, choices=AccountType.choices)
    currency = models.CharField(max_length=3, default="TZS")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    description = models.CharField(max_length=255, blank=True)

    group = models.ForeignKey(
        "groups.VikobaGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_accounts",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_accounts",
    )
    savings_account = models.OneToOneField(
        "accounts.SavingsAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_account",
        help_text="Linked operational savings account for member-scoped accounts.",
    )
    loan_account = models.OneToOneField(
        "loans.LoanAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_account",
        help_text="Linked operational loan account for receivable accounts.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["account_number"]

    def __str__(self):
        return f"{self.account_number} - {self.name}"

    @property
    def is_liability_or_equity_or_income(self):
        return self.account_type in {
            self.AccountType.LIABILITY,
            self.AccountType.EQUITY,
            self.AccountType.INCOME,
        }


class FinancialTransaction(models.Model):
    """The central, single-source financial transaction record.

    References are human-readable and unique (see ``ReferenceCounter``). A
    transaction is only ever posted with a balanced journal, and successful
    transactions are never removed from the database — reversal creates a new
    transaction linked via ``reversal_of``.
    """

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        REVERSED = "REVERSED", "Reversed"
        REFUNDED = "REFUNDED", "Refunded"
        RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED", "Needs reconciliation"

    class TransactionType(models.TextChoices):
        CONTRIBUTION = "CONTRIBUTION", "Contribution"
        DEPOSIT = "DEPOSIT", "Deposit"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan disbursement"
        LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
        INTEREST = "INTEREST", "Interest"
        PENALTY = "PENALTY", "Penalty"
        REFUND = "REFUND", "Refund"
        TRANSFER = "TRANSFER", "Transfer"
        GROUP_EXPENSE = "GROUP_EXPENSE", "Group expense"
        MEMBERSHIP_FEE = "MEMBERSHIP_FEE", "Membership fee"
        PLATFORM_FEE = "PLATFORM_FEE", "Platform fee"
        PROVIDER_FEE = "PROVIDER_FEE", "Provider fee"
        SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        REVERSAL = "REVERSAL", "Reversal"

    reference = models.CharField(max_length=60, unique=True, editable=False, db_index=True)
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    group = models.ForeignKey(
        "groups.VikobaGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.INITIATED, db_index=True
    )
    description = models.CharField(max_length=255, blank=True)

    external_reference = models.CharField(max_length=120, blank=True)
    provider = models.CharField(max_length=30, blank=True)
    provider_transaction_id = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Provider-side reference (only set when we uniquely know it).",
    )

    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Guarantees a repeated request can never create a second transaction.",
    )

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversals",
    )
    reversal_reason = models.CharField(max_length=255, blank=True)

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_financial_transactions",
    )

    # Optional links back to the operational records that funded this entry.
    loan = models.ForeignKey(
        "loans.LoanAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
        help_text="Loan this journal belongs to (loan-specific journals only).",
    )
    payment_transaction = models.ForeignKey(
        "payments.PaymentTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    savings_transaction = models.ForeignKey(
        "accounts.SavingsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    deposit_request = models.ForeignKey(
        "accounts.DepositRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    withdrawal_request = models.ForeignKey(
        "accounts.WithdrawalRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )
    contribution = models.ForeignKey(
        "groups.GroupContribution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_transactions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.reference} - {self.status}"

    @property
    def is_terminal(self):
        return self.status in {
            self.Status.SUCCESS,
            self.Status.FAILED,
            self.Status.CANCELLED,
            self.Status.REVERSED,
            self.Status.REFUNDED,
        }

    @property
    def debits(self):
        return self.entries.filter(entry_type=JournalEntry.DEBIT)

    @property
    def credits(self):
        return self.entries.filter(entry_type=JournalEntry.CREDIT)


class JournalEntry(models.Model):
    """One leg of a double-entry posting.

    Direction is expressed by ``entry_type`` — amounts are always positive.
    A journal is only valid when ``SUM(DEBITS) == SUM(CREDITS)``.
    """

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    ENTRY_TYPE_CHOICES = [(DEBIT, "Debit"), (CREDIT, "Credit")]

    transaction = models.ForeignKey(
        FinancialTransaction,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    entry_type = models.CharField(max_length=6, choices=ENTRY_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    description = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="journal_entry_positive_amount",
            ),
            models.UniqueConstraint(
                fields=["transaction", "position"], name="unique_journal_entry_position"
            ),
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount} on {self.account.account_number}"


class AuditEvent(models.Model):
    """Append-only financial audit trail.

    Created inside the same database transaction as the event it describes
    (transaction created/posted/failed/reversed). Never logs secrets.
    """

    ACTION_TRANSACTION_CREATED = "financial_transaction.created"
    ACTION_TRANSACTION_POSTED = "financial_transaction.posted"
    ACTION_TRANSACTION_FAILED = "financial_transaction.failed"
    ACTION_TRANSACTION_REVERSED = "financial_transaction.reversed"
    ACTION_TRANSACTION_CANCELLED = "financial_transaction.cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_audit_events",
    )
    action = models.CharField(max_length=60, db_index=True)
    reference = models.CharField(max_length=60, blank=True, db_index=True)
    transaction = models.ForeignKey(
        FinancialTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} {self.reference}"