"""KYC API views.

Member endpoints:
- GET  /kyc/me/                      current KYC profile + masked identity summary
- POST /kyc/me/verify/               submit (idempotent) verification
- GET  /kyc/me/requests/             the member's verification history (masked)
- GET  /kyc/me/timeline/             safe KYC event timeline

Staff endpoints (business roles only — never members):
- GET  /kyc/admin/                   dashboard + filters + summary counts
- GET  /kyc/admin/<membership_number>/   profile + results + audit trail
- POST /kyc/admin/<membership_number>/review/  audited manual approve/reject/update

Group isolation: members can only ever reach their own KYC via ``/kyc/me``;
staff KYC views are member-agnostic staff endpoints, never group-scoped for
officers (a Treasurer sees a withdrawal approval, not raw identity data).
"""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from kyc import services
from kyc.models import KYCEvent, KYCProfile, KYCVerificationRequest
from kyc.serializers import (
    KYCAdminProfileSerializer,
    KYCEventSerializer,
    KYCProfileSerializer,
    KYCReviewSerializer,
    KYCVerificationRequestSerializer,
    KYCVerifySubmitSerializer,
)
from members.models import Member
from users.permissions import HasMemberAccess, IsMember

User = get_user_model()


def _member_for(request):
    try:
        return request.user.member
    except Member.DoesNotExist:
        return None


# --------------------------------------------------------------------------- #
# Member self-service
# --------------------------------------------------------------------------- #

class MeKYCProfileView(GenericAPIView):
    permission_classes = [IsMember]
    serializer_class = KYCProfileSerializer

    def get(self, request):
        member = _member_for(request)
        if member is None:
            return Response({"detail": "No member profile linked to this account."}, status=status.HTTP_400_BAD_REQUEST)
        profile = services.get_or_create_profile(member)
        services.check_expiry(profile)
        return Response(KYCProfileSerializer(profile).data)


class MeKYCVerifyView(GenericAPIView):
    permission_classes = [IsMember]
    serializer_class = KYCVerifySubmitSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "kyc-submit"

    def post(self, request):
        member = _member_for(request)
        if member is None:
            return Response({"detail": "No member profile linked to this account."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = (serializer.validated_data.get("idempotency_key") or "").strip() or None
        try:
            result = services.submit_verification(
                member=member,
                idempotency_key=key,
                actor=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except services.KYCError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile = result["profile"]
        return Response(
            {
                "profile": KYCProfileSerializer(profile).data,
                "request": KYCVerificationRequestSerializer(result["request"]).data,
            }
        )


class MeKYCRequestsView(GenericAPIView):
    permission_classes = [IsMember]
    serializer_class = KYCVerificationRequestSerializer

    def get(self, request):
        member = _member_for(request)
        if member is None:
            return Response({"detail": "No member profile linked to this account."}, status=status.HTTP_400_BAD_REQUEST)
        profile = services.get_or_create_profile(member)
        requests = profile.requests.order_by("-submitted_at")
        return Response(KYCVerificationRequestSerializer(requests, many=True).data)


class MeKYCTimelineView(GenericAPIView):
    permission_classes = [IsMember]
    serializer_class = KYCEventSerializer

    def get(self, request):
        member = _member_for(request)
        if member is None:
            return Response({"detail": "No member profile linked to this account."}, status=status.HTTP_400_BAD_REQUEST)
        profile = services.get_or_create_profile(member)
        events = profile.events.order_by("-created_at")[:50]
        return Response(KYCEventSerializer(events, many=True).data)


# --------------------------------------------------------------------------- #
# Staff admin
# --------------------------------------------------------------------------- #

class KYCAdminOverviewView(GenericAPIView):
    permission_classes = [HasMemberAccess]
    serializer_class = KYCAdminProfileSerializer

    def get(self, request):
        params = request.query_params
        status_filter = params.get("status") or None
        level = params.get("level") or None
        group_id = params.get("group") or None
        search = params.get("search") or None
        from_date = params.get("verified_from") or None
        to_date = params.get("verified_to") or None

        qs = services.admin_profiles(
            status=status_filter,
            level=level,
            group_id=group_id,
            search=search,
            verified_from=from_date,
            verified_to=to_date,
        )
        data = KYCAdminProfileSerializer(qs[:300], many=True).data
        return Response({"summary": services.dashboard_summary(), "profiles": data})


class KYCAdminDetailView(GenericAPIView):
    permission_classes = [HasMemberAccess]
    serializer_class = KYCAdminProfileSerializer

    def get(self, request, membership_number=None):
        member = get_object_or_404(Member, membership_number=membership_number)
        profile = services.get_or_create_profile(member)
        services.check_expiry(profile)
        data = KYCAdminProfileSerializer(profile).data
        events = profile.events.order_by("-created_at")[:100]
        data["events"] = KYCEventSerializer(events, many=True).data
        return Response(data)


class KYCAdminReviewView(GenericAPIView):
    """Authorised staff manual review — every decision is audited."""

    permission_classes = [HasMemberAccess]
    serializer_class = KYCReviewSerializer

    def post(self, request, membership_number=None):
        member = get_object_or_404(Member, membership_number=membership_number)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        reason = serializer.validated_data["reason"]
        try:
            result = services.manual_review(
                member=member,
                decision=decision,
                reason=reason,
                actor=request.user,
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        except services.KYCError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile = result["profile"]
        return Response(KYCAdminProfileSerializer(profile).data)