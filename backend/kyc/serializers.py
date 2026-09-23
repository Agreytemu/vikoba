"""KYC API serializers. Sensitive provider/identity values are masked."""
from rest_framework import serializers

from kyc.models import KYCEvent, KYCProfile, KYCVerificationRequest
from kyc.services import current_status
from kyc.utils import mask_identifier, mask_name


class KYCIdentitySummarySerializer(serializers.Serializer):
    full_name = serializers.CharField()
    national_id = serializers.CharField()          # already masked by the service
    date_of_birth = serializers.CharField()
    complete = serializers.BooleanField()


class KYCProfileSerializer(serializers.ModelSerializer):
    """Member-safe view of the current KYC state."""

    identity_summary = serializers.SerializerMethodField()
    required_level = serializers.SerializerMethodField()
    eligible = serializers.SerializerMethodField()
    eligible_level_2 = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    level_label = serializers.CharField(source="get_verification_level_display", read_only=True)

    class Meta:
        model = KYCProfile
        fields = [
            "status",
            "status_label",
            "verification_level",
            "level_label",
            "verification_method",
            "provider",
            "provider_reference",
            "verified_at",
            "expires_at",
            "last_checked_at",
            "failure_code",
            "failure_reason",
            "identity_summary",
            "required_level",
            "eligible",
            "eligible_level_2",
        ]
        read_only_fields = fields

    def get_identity_summary(self, obj):
        return current_status(obj.member)["identity_summary"]

    def get_required_level(self, obj):
        from kyc.services import required_level_default

        return required_level_default()

    def get_eligible(self, obj):
        return obj.status == "VERIFIED" and not obj.expired

    def get_eligible_level_2(self, obj):
        from kyc.statuses import KYCLevel

        return obj.status == "VERIFIED" and not obj.expired and obj.verification_level == KYCLevel.LEVEL_2


class KYCVerificationRequestSerializer(serializers.ModelSerializer):
    """Member-facing request + stored result (masked references, match flags only)."""

    provider_reference = serializers.SerializerMethodField()
    verified_name = serializers.SerializerMethodField()

    class Meta:
        model = KYCVerificationRequest
        fields = [
            "request_ref",
            "status",
            "attempt_count",
            "max_attempts",
            "provider",
            "provider_reference",
            "verification_status",
            "failure_code",
            "failure_reason",
            "match_result",
            "verified_name",
            "verified_dob",
            "submitted_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_provider_reference(self, obj):
        return mask_identifier(obj.provider_reference, keep=6)

    def get_verified_name(self, obj):
        return mask_name(obj.verified_name)


class KYCEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = KYCEvent
        fields = [
            "action",
            "status",
            "from_status",
            "to_status",
            "provider",
            "provider_reference",
            "failure_code",
            "actor_name",
            "actor_type",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor is None:
            return ""
        return f"{obj.actor.get_full_name() or obj.actor.email}"


class KYCAdminProfileSerializer(serializers.ModelSerializer):
    """Staff dashboard view. National ID masked; request details listed."""

    membership_number = serializers.CharField(source="member.membership_number", read_only=True)
    member_name = serializers.SerializerMethodField()
    national_id = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    requests = KYCVerificationRequestSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = KYCProfile
        fields = [
            "membership_number",
            "member_name",
            "national_id",
            "groups",
            "status",
            "status_label",
            "verification_level",
            "verification_method",
            "provider",
            "provider_reference",
            "verified_at",
            "expires_at",
            "last_checked_at",
            "failure_code",
            "failure_reason",
            "requests",
        ]
        read_only_fields = fields

    def get_member_name(self, obj):
        m = obj.member
        return f"{m.first_name or ''} {m.last_name or ''}".strip()

    def get_national_id(self, obj):
        return mask_identifier(obj.member.national_id, keep=4)

    def get_groups(self, obj):
        return [
            {
                "id": ms.group_id,
                "name": ms.group.name,
                "role": ms.role,
            }
            for ms in obj.member.group_memberships.filter(is_active=True)
        ]

    def get_provider_reference(self, obj):
        return mask_identifier(obj.provider_reference, keep=6)


class KYCReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject", "request_update"])
    reason = serializers.CharField(max_length=500)


class KYCVerifySubmitSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=120, required=False, allow_blank=True)