from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Member, KYCDocument, PhoneOTP
from .serializers import (
    MeMemberSerializer,
    MemberSerializer,
    NextOfKinSerializer,
    KYCDocumentSerializer,
    PhoneOTPRequestSerializer,
    PhoneOTPVerifySerializer,
    VerificationStatusSerializer,
)
from users.permissions import HasMemberAccess
from payments.utils.phone import detect_network


class MemberViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    queryset = Member.objects.all().prefetch_related("next_of_kin")
    serializer_class = MemberSerializer
    permission_classes = [HasMemberAccess]
    lookup_field = "membership_number"

    def upload_kyc_document(self, request, membership_number=None):
        """Upload one KYC document using multipart form data."""
        member = self.get_object()
        serializer = KYCDocumentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(member=member)
        return Response(serializer.data, status=201)


def _member_for(request):
    """Return the authenticated member's own profile or None when not linked."""
    try:
        return request.user.member
    except Member.DoesNotExist:
        return None


class MemberMeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH the authenticated member's own profile."""
    serializer_class = MeMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        member = _member_for(self.request)
        if member is None:
            return None
        return member

    def get(self, request, *args, **kwargs):
        member = self.get_object()
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(member)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        member = self.get_object()
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MemberMeVerificationStatusView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        member = _member_for(self.request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VerificationStatusSerializer(member)
        return Response(serializer.data)


class MemberMeNextOfKinView(generics.ListCreateAPIView):
    serializer_class = NextOfKinSerializer
    permission_classes = [IsAuthenticated]

    def get_member(self):
        member = _member_for(self.request)
        return member

    def get_queryset(self):
        member = self.get_member()
        if member is None:
            return NextOfKin.objects.none()
        return member.next_of_kin.all()

    def create(self, request, *args, **kwargs):
        member = self.get_member()
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(member=member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MemberMeKYCDocumentsView(generics.ListCreateAPIView):
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_member(self):
        return _member_for(self.request)

    def get_queryset(self):
        member = self.get_member()
        if member is None:
            return KYCDocument.objects.none()
        return member.kyc_documents.all()

    def create(self, request, *args, **kwargs):
        member = self.get_member()
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(member=member)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MemberMePhoneOTPRequestView(generics.GenericAPIView):
    serializer_class = PhoneOTPRequestSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        member = _member_for(self.request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 120)
        latest = (
            PhoneOTP.objects
            .filter(member=member, phone_number=phone_number)
            .order_by("-created_at", "-pk")
            .first()
        )
        if latest is not None:
            elapsed = (timezone.now() - latest.created_at).total_seconds()
            wait = int(cooldown - elapsed) + 1
            if elapsed < cooldown:
                return Response(
                    {"detail": f"Please wait {max(wait, 1)} seconds before requesting another code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        otp = PhoneOTP.issue(member, phone_number)
        data = {
            "phone_number": otp.phone_number,
            "expires_in_minutes": PhoneOTP.TTL_MINUTES,
            "dev_mode": settings.OTP_DEV_MODE,
        }

        if settings.OTP_DEV_MODE:
            data["dev_code"] = otp.code

        return Response(data)


class MemberMePhoneOTPVerifyView(generics.GenericAPIView):
    serializer_class = PhoneOTPVerifySerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        member = _member_for(self.request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        otp = (
            PhoneOTP.objects
            .filter(member=member, phone_number=phone_number, is_used=False)
            .first()
        )
        if otp is None:
            return Response(
                {"detail": "No pending verification code for this phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.is_valid(code):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            return Response(
                {"detail": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        member.phone_number = phone_number
        member.phone_verified = True
        member.phone_network = detect_network(phone_number)
        member.refresh_verification()
        member.save(
            update_fields=[
                "phone_number",
                "phone_verified",
                "phone_network",
                "is_verified",
                "updated_at",
            ]
        )
        return Response(VerificationStatusSerializer(member).data)


class MemberMeSubmitForReviewView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        member = _member_for(self.request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member.verification_submitted = True
        member.refresh_verification()
        member.save(update_fields=["verification_submitted", "is_verified", "updated_at"])
        return Response(VerificationStatusSerializer(member).data)


class MemberKYCVerifyView(generics.GenericAPIView):
    """
    Staff-only: mark a member's KYC document as verified. Member becomes
    verified automatically once all verification steps are complete.
    """
    permission_classes = [HasMemberAccess]

    def post(self, request, membership_number, doc_id):
        member = get_object_or_404(Member, membership_number=membership_number)
        document = get_object_or_404(KYCDocument, id=doc_id, member=member)
        if not document.verified:
            document.verified = True
            document.verified_by = request.user
            document.save(update_fields=["verified", "verified_by"])
            member.refresh_verification()
            member.save(update_fields=["is_verified", "updated_at"])
        return Response(KYCDocumentSerializer(document).data)


class MemberMeOnboardingView(generics.GenericAPIView):
    """Save onboarding details (address, citizenship, gender, DOB, job, currency, plan).

    The standalone onboarding wizard runs all verification steps (phone, KYC,
    next of kin) and finishes with this call. Credential checks are relaxed for
    now (UI-only flow); real enforcement gets re-enabled later.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None:
            return Response({"detail": "No member profile is linked to this account."}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data
        # Validate age >=18
        from datetime import date
        dob = data.get("date_of_birth")
        if dob:
            try:
                y, m, d = map(int, str(dob).split("-"))
                dob_date = date(y, m, d)
                today = date.today()
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                if age < 18:
                    return Response({"detail": "You must be at least 18 years old."}, status=status.HTTP_400_BAD_REQUEST)
                member.date_of_birth = dob_date
            except Exception:
                return Response({"detail": "Invalid date_of_birth (use YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        # Simple field updates
        for field in ["permanent_address", "street", "region", "citizenship_type", "gender", "occupation", "preferred_currency"]:
            if field in data and data[field] not in (None, ""):
                setattr(member, field, data[field])
        # Currency only TZS/USD
        if member.preferred_currency not in ("TZS", "USD"):
            member.preferred_currency = "TZS"
        # Plan: admin-created, can be null (Free)
        plan_id = data.get("selected_plan")
        if plan_id:
            from accounts.models import MembershipPlan
            try:
                plan = MembershipPlan.objects.get(pk=plan_id, is_active=True)
                member.selected_plan = plan
            except MembershipPlan.DoesNotExist:
                return Response({"detail": "Selected plan not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            member.selected_plan = None
        member.is_onboarded = True
        from django.utils import timezone as _tz
        member.onboarded_at = _tz.now()
        if not member.country:
            member.country = "Tanzania"
        member.save()

        # Every member gets their own savings account automatically, so they can
        # deposit/withdraw from their wallet without waiting for staff.
        from accounts.models import SavingsAccount, SavingsProduct
        product, _ = SavingsProduct.objects.get_or_create(
            code="BASIC",
            defaults={
                "name": "Basic Savings",
                "minimum_balance": 0,
                "interest_rate": 0,
                "withdrawal_fee": 0,
                "allows_withdrawals": True,
                "is_active": True,
            },
        )
        SavingsAccount.objects.get_or_create(member=member, product=product)

        return Response(MeMemberSerializer(member).data)