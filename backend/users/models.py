from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from .managers import UserManager


class User(AbstractUser):
    ADMIN = "AD"
    MANAGER = "MA"
    OPERATION = "OP"
    FINANCE = "FI"
    LOAN = "LO"
    ACCOUNTANT = "AC"
    MEMBER = "ME"

    ROLE_CHOICES = (
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (OPERATION, 'Operation Manager'),
        (FINANCE, 'Finance Officer'),
        (LOAN, 'Loan Officer'),
        (ACCOUNTANT, 'Accountant'),
        (MEMBER, 'Member'),
    )

    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(
        default=False,
        help_text="Is the email address confirmed via the 6-digit email code?",
    )
    role = models.CharField(
        max_length=2,
        choices=ROLE_CHOICES,
        default=ACCOUNTANT
    )
    profile_image = models.ImageField(
        upload_to='users',
        blank=True,
        null=True
    )

    # 4-digit quick-login PIN ("namba za siri"). Stored as a Django password
    # hash, never in plain text. Members use phone + PIN on the PWA to skip the
    # long password; wrong guesses are counted and the PIN locks after a few.
    PIN_MAX_ATTEMPTS = 5
    PIN_LOCK_MINUTES = 10

    pin_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Hashed 4-digit quick-login PIN (empty = PIN not set)",
    )
    pin_attempts = models.PositiveIntegerField(default=0)
    pin_locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Until when the quick-login PIN is temporarily locked.",
    )

    USERNAME_FIELD = 'email'   #  login with email
    REQUIRED_FIELDS = ['username']  #  still required for superuser

    def __str__(self):
        return self.email

    objects = UserManager()

    @property
    def has_pin(self) -> bool:
        return bool(self.pin_hash)

    @property
    def is_pin_locked(self) -> bool:
        return (
            self.pin_locked_until is not None
            and self.pin_locked_until > timezone.now()
        )

    def set_pin(self, pin: str) -> None:
        """Store the 4-digit PIN as a hash and reset any lockout state."""
        from django.contrib.auth.hashers import make_password
        self.pin_hash = make_password(pin)
        self.pin_attempts = 0
        self.pin_locked_until = None


class EmailVerificationCode(models.Model):
    """One-time, expiring 6-digit code used to verify a user's email address."""

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 30

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification_codes",
    )
    code = models.CharField(max_length=6)
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.user.email} -> {self.code}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_valid(self) -> bool:
        return (
            not self.is_used
            and not self.is_expired
            and not self.is_exhausted
            and self.code
        )

    @property
    def is_exhausted(self) -> bool:
        return self.attempts >= self.MAX_ATTEMPTS


class PinSetupCode(models.Model):
    """One-time, expiring code emailed to a member to authorize setting (or
    resetting) the 4-digit quick-login PIN.

    The code is delivered to the account's verified email, so anyone setting a
    PIN must first prove access to the account's email.
    """

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 15

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pin_setup_codes",
    )
    code = models.CharField(max_length=6)
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.user.email} -> {self.code}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_valid(self) -> bool:
        return (
            not self.is_used
            and not self.is_expired
            and not self.is_exhausted
            and self.code
        )

    @property
    def is_exhausted(self) -> bool:
        return self.attempts >= self.MAX_ATTEMPTS


class Notification(models.Model):
    """In-app alert for a user (optionally mirrored to SMS)."""

    class Kind(models.TextChoices):
        INFO = "info", "Info"
        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        LOAN = "loan", "Loan"
        GROUP = "group", "Group"
        SHARE_OUT = "share_out", "Share-out"
        MEETING = "meeting", "Meeting"
        ANNOUNCEMENT = "announcement", "Announcement"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=120)
    body = models.TextField(blank=True)
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.INFO,
    )
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
