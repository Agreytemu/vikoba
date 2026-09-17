from django.db import models, transaction
from django.conf import settings


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
        REJECTED = "REJECTED", "Rejected"

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
