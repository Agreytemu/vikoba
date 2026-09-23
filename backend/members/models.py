from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
import uuid
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


class MemberSequence(models.Model):
    last_value = models.PositiveIntegerField(default=0)


def generate_membership_number():
    """
    Generate membership number
    """
    seq, _ = MemberSequence.objects.select_for_update().get_or_create(id=1)
    seq.last_value += 1
    seq.save()
    return f"M{seq.last_value:06d}"


class Member(models.Model):
    """
    Member/Customer model contains personal details, membership number and status life cycle
    """
    class Salutation(models.TextChoices):
        MR = 'Mr', _('Mr.')
        MRS = 'Mrs', _('Mrs.')
        MS = 'Ms', _('Ms.')
        DR = 'Dr', _('Dr.')
        PROF = 'Prof', _('Prof.')
        REV = 'Rev', _('Rev.')

    class Status(models.TextChoices):
        ACTIVE = 'Active', _('Active')
        CLOSED = 'Closed', _('Closed')
        DORMANT = 'Dormant', _('Dormant')
        SUSPENDED = 'Suspended', _('Suspended')
        PENDING = 'Pending', _("Pending")

    class RegistrationSource(models.TextChoices):
        SELF = 'SELF', _('Self registration')
        ADMIN = 'ADMIN', _('Created by staff')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Membership details
    membership_number = models.CharField(
        max_length=20, unique=True, editable=False)

    # Login account (set when a member self-registers)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="member",
    )

    # Personal details
    salutation = models.CharField(
        max_length=5, choices=Salutation.choices, default=Salutation.MR)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    kra_pin = models.CharField(max_length=100, blank=True, null=True)
    # Address
    country = models.CharField(max_length=100, blank=True, default="Tanzania")
    county = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    permanent_address = models.CharField(max_length=255, blank=True)
    street = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True)

    # Onboarding — Tanzania specific
    class CitizenshipType(models.TextChoices):
        BY_BIRTH = "BY_BIRTH", _("By birth")
        NATURALIZATION = "NATURALIZATION", _("By naturalization / application")
        MARRIAGE = "MARRIAGE", _("By marriage")

    class Gender(models.TextChoices):
        MALE = "MALE", _("Male")
        FEMALE = "FEMALE", _("Female")

    citizenship_type = models.CharField(max_length=20, choices=CitizenshipType.choices, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    preferred_currency = models.CharField(max_length=3, choices=[("TZS", "TZS"), ("USD", "USD")], default="TZS")
    is_onboarded = models.BooleanField(default=False)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    selected_plan = models.ForeignKey("accounts.MembershipPlan", null=True, blank=True, on_delete=models.SET_NULL, related_name="members")

    # Status
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )

    # Verification pipeline for self-registered members
    registration_source = models.CharField(
        max_length=10,
        choices=RegistrationSource.choices,
        default=RegistrationSource.ADMIN,
    )
    phone_verified = models.BooleanField(default=False)
    # Snippe mobile-money network of the verified number (M-Pesa, Airtel, Mixx,
    # Halotel). "unknown" until a number is verified.
    class PhoneNetwork(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        AIRTEL = "airtel", "Airtel Money"
        MIXX = "mixx", "Mixx by Yas"
        HALOTEL = "halotel", "Halotel"
        UNKNOWN = "unknown", "Unknown"

    phone_network = models.CharField(
        max_length=10,
        choices=PhoneNetwork.choices,
        default=PhoneNetwork.UNKNOWN,
        blank=True,
    )
    verification_submitted = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, db_index=True)

    # Dates
    date_joined = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_kyc_complete(self):
        required = {"NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"}
        uploaded = set(
            self.kyc_documents.filter(verified=True)
            .values_list("document_type", flat=True)
        )
        return required.issubset(uploaded)

    def verification_status(self):
        """
        Fine-grained verification progress used by the member onboarding UI
        and the verification-status endpoint.
        """
        return {
            "is_verified": self.is_verified,
            "phone_verified": self.phone_verified,
            "phone_network": self.phone_network,
            "kyc_complete": self.is_kyc_complete(),
            "next_of_kin_added": self.next_of_kin.exists(),
            "submitted": self.verification_submitted,
        }

    def refresh_verification(self):
        """
        Recompute is_verified from the verification pipeline.

        - Staff-created members are trusted already (the branch is chosen and
          onboarded by the platform) and stay verified.
        - Self-registered members become verified once they have submitted for
          review, verified their phone and completed KYC + next of kin.

        The authoritative KYC layer (``kyc`` app) is kept in sync so the
        financial engines can consume a single, audited verification state.
        """
        changed = False
        if self.registration_source == self.RegistrationSource.ADMIN:
            if not self.is_verified:
                self.is_verified = True
                changed = True
        elif (
            self.verification_submitted
            and self.phone_verified
            and self.next_of_kin.exists()
            and self.is_kyc_complete()
        ):
            if not self.is_verified:
                self.is_verified = True
                changed = True

        if changed:
            from kyc import services as kyc_services

            kyc_services.sync_from_member(self)

    def save(self, *args, **kwargs):
        if not self.membership_number:
            with transaction.atomic():
                self.membership_number = generate_membership_number()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["membership_number"]

    def __str__(self):
        return self.membership_number


class NextOfKin(models.Model):
    """
    NextOfKin model supports multiple next of kin 
    """
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="next_of_kin"
    )

    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    national_id = models.CharField(max_length=20, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class EmploymentDetail(models.Model):
    """
    Members employment details:
    - Salaried members
    - Business owner 
    - Self-employed members
    """

    EMPLOYMENT_TYPE_CHOICES = (
        ("EMPLOYED", "Employed"),
        ("SELF_EMPLOYED", "Self Employed"),
        ("BUSINESS", "Business Owner"),
        ("UNEMPLOYED", "Unemployed"),
    )

    member = models.OneToOneField(
        Member, on_delete=models.CASCADE, related_name="employment"
    )

    employment_type = models.CharField(
        max_length=20, choices=EMPLOYMENT_TYPE_CHOICES
    )

    employer_name = models.CharField(max_length=255, blank=True, null=True)
    job_title = models.CharField(max_length=255, blank=True, null=True)
    monthly_income = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )

    business_name = models.CharField(max_length=255, blank=True, null=True)
    business_type = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member} - {self.employment_type}"


def kyc_upload_path(instance, filename):
    return f"kyc/{instance.member.membership_number}/{filename}"


class KYCDocument(models.Model):
    """
    KYCDocument supports: ID upload, Passport photo, Signature
    A member is considered KYC-complete when:
    - All required document types exist
    - All are verified
    Stuff member reviews uploaded documents, confirms correctness, marks them as verified = True. System records verified_by, uploaded_at
    """
    DOCUMENT_TYPE_CHOICES = (
        ("NATIONAL_ID", "National ID"),
        ("PASSPORT_PHOTO", "Passport Photo"),
        ("SIGNATURE", "Signature"),
    )

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="kyc_documents"
    )

    document_type = models.CharField(
        max_length=30, choices=DOCUMENT_TYPE_CHOICES
    )

    file = models.FileField(upload_to=kyc_upload_path)

    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_kyc_documents",
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member} - {self.document_type}"


class PhoneOTP(models.Model):
    """
    One-time password used to verify a member's phone number during
    self-service onboarding. Real SMS delivery is not wired up yet, so in
    OTP_DEV_MODE the issued code is returned to the client as dev_code.
    """

    PURPOSE_VERIFY_PHONE = "VERIFY_PHONE"

    PURPOSE_CHOICES = (
        (PURPOSE_VERIFY_PHONE, "Verify phone"),
    )

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 10

    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="otps"
    )
    phone_number = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default=PURPOSE_VERIFY_PHONE
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, member, phone_number):
        """Invalidate previous unused codes and create a fresh one."""
        cls.objects.filter(
            member=member, phone_number=phone_number, is_used=False
        ).update(is_used=True)
        code = f"{secrets.randbelow(1_000_000):06d}"
        return cls.objects.create(
            member=member,
            phone_number=phone_number,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.TTL_MINUTES),
        )

    def is_valid(self, code):
        if self.is_used:
            return False
        if self.expires_at < timezone.now():
            return False
        if self.attempts >= self.MAX_ATTEMPTS:
            return False
        return self.code == code

    def __str__(self):
        return f"{self.member} otp"
