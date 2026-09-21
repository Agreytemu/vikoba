import calendar
from datetime import timedelta

from django.db import models, transaction
from django.conf import settings
from django.utils import timezone


class MembershipPlan(models.Model):
    """Monthly plan created by admin — not hardcoded. Selected at onboarding end."""
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, choices=[("TZS", "TZS"), ("USD", "USD")], default="TZS")
    interval = models.CharField(max_length=20, default="monthly")
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.price} {self.currency}/{self.interval}"


def plan_period_end(start, interval):
    """Next billing date for a subscription started at `start`.

    Defaults to one calendar month ahead; weekly/yearly/daily intervals are
    honoured too. The expiry is the NEXT billing date, i.e. one full period
    after the start.
    """
    interval = (interval or "").strip().lower()
    if interval in ("yearly", "year", "annual"):
        return start + timedelta(days=365)
    if interval in ("weekly", "week"):
        return start + timedelta(days=7)
    if interval in ("daily", "day"):
        return start + timedelta(days=1)
    # Default: advance by one calendar month (clamped to the month's length).
    month = start.month - 1 + 1
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class MemberSubscription(models.Model):
    """A member's plan subscription lifecycle.

    Created PENDING at the checkout; it is only ever flipped to ACTIVE by the
    verified Snippe ``payment.completed`` webhook — never by the initiation
    request, so an unanswered or failed payment never activates a plan.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    payment = models.ForeignKey(
        "payments.PaymentTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def activate(self):
        """Mark the subscription live with start + next-billing dates."""
        now = timezone.now()
        self.started_at = now
        self.expires_at = plan_period_end(now, self.plan.interval)
        self.status = self.Status.ACTIVE
        self.save(update_fields=["started_at", "expires_at", "status", "updated_at"])

    def __str__(self):
        return f"{self.member} · {self.plan.name} · {self.status}"


def generate_account_number():
    # Row lock guards against two concurrent account creations deriving the
    # same number. Must run inside a transaction (SavingsAccount.save wraps
    # the call) for the lock to be meaningful.
    last = SavingsAccount.objects.select_for_update().order_by("-id").first()
    next_id = (last.id + 1) if last else 1
    return f"SA{next_id:08d}"


class SavingsProduct(models.Model):
    """
        This models id used to create account types e.g fixed account, current account
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)

    minimum_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)

    withdrawal_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    allows_withdrawals = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SavingsAccount(models.Model):
    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="accounts"
    )

    product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.PROTECT
    )

    account_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True
    )

    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(default=True)
    opened_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            with transaction.atomic():
                self.account_number = generate_account_number()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("member", "product")

    def __str__(self):
        return f"{self.account_number} - {self.member}"


class SavingsTransaction(models.Model):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    INTEREST = "interest"
    ADJUSTMENT = "adjustment"

    TRANSACTION_TYPES = [
        (DEPOSIT, "Deposit"),
        (WITHDRAWAL, "Withdrawal"),
        (INTEREST, "Interest"),
        (ADJUSTMENT, "Adjustment"),
    ]

    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="transactions"
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    reference = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    narration = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_type} - {self.amount}"


def _request_reference(prefix):
    import uuid
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:6].upper()}"


class DepositRequest(models.Model):
    """A member-initiated deposit (e.g. M-Pesa) that staff must approve."""

    class Channel(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CASH = "cash", "Cash"
        BANK = "bank", "Bank transfer"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="deposit_requests",
    )
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="deposit_requests",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        default=Channel.MPESA,
    )
    transaction_code = models.CharField(max_length=80, blank=True)
    reference = models.CharField(max_length=50, unique=True, editable=False)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_deposits",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _request_reference("DEP")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.amount}"


class WithdrawalRequest(models.Model):
    """A member-initiated withdrawal (verified members) approved by staff."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        SENT_TO_SNIPPE = "SENT_TO_SNIPPE", "Sent to Snippe"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="withdrawal_requests",
    )
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="withdrawal_requests",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    narration = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=50, unique=True, editable=False)
    status = models.CharField(
        max_length=14,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_withdrawals",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _request_reference("WDR")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.amount}"
