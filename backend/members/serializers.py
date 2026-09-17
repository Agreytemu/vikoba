from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Member, NextOfKin, EmploymentDetail, KYCDocument
from .validators import validate_uploaded_file


class NextOfKinSerializer(serializers.ModelSerializer):
    class Meta:
        model = NextOfKin
        exclude = ("member", "created_at")


class EmploymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentDetail
        exclude = ("member", "created_at")


class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        exclude = ("member", "uploaded_at")
        extra_kwargs = {
            "file": {"validators": [validate_uploaded_file]},
            "verified": {"read_only": True},
            "verified_by": {"read_only": True},
        }


class MemberSerializer(WritableNestedModelSerializer):
    next_of_kin = NextOfKinSerializer(many=True, required=False)
    employment = EmploymentDetailSerializer(many=False)
    # Files are uploaded separately via the multipart KYC endpoint so member
    # create and update requests can remain JSON.
    kyc_documents = KYCDocumentSerializer(many=True, required=False)

    class Meta:
        model = Member
        exclude = ("date_joined", "created_at", "updated_at")
        extra_kwargs = {
            'national_id': {
                'validators': [
                    UniqueValidator(
                        queryset=Member.objects.all(),
                        message="A member with this national ID already exists.",
                    )
                ]
            }
        }


class MeMemberSerializer(serializers.ModelSerializer):
    """
    Self-service view of the authenticated member's own profile. Staff-only
    fields (user account details, registration bookkeeping) are excluded and a
    read-only verification breakdown is included for the onboarding UI.
    """
    next_of_kin = NextOfKinSerializer(many=True, read_only=True)
    employment = EmploymentDetailSerializer(read_only=True)
    verification = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Member
        fields = (
            "membership_number",
            "salutation",
            "first_name",
            "middle_name",
            "last_name",
            "phone_number",
            "email",
            "date_of_birth",
            "national_id",
            "kra_pin",
            "country",
            "county",
            "city",
            "permanent_address",
            "street",
            "region",
            "citizenship_type",
            "gender",
            "occupation",
            "preferred_currency",
            "is_onboarded",
            "onboarded_at",
            "selected_plan",
            "status",
            "phone_verified",
            "is_verified",
            "verification",
            "next_of_kin",
            "employment",
        )
        read_only_fields = (
            "membership_number",
            "status",
            "phone_verified",
            "is_verified",
            "verification",
            "next_of_kin",
            "employment",
        )

    def get_verification(self, obj):
        return obj.verification_status()

    def update(self, instance, validated_data):
        phone_changed = (
            "phone_number" in validated_data
            and validated_data["phone_number"] != instance.phone_number
        )
        instance = super().update(instance, validated_data)
        if phone_changed:
            # A new phone number must be verified again before the member is
            # considered verified.
            instance.phone_verified = False
            instance.is_verified = False
            instance.refresh_verification()
            instance.save(update_fields=["phone_verified", "is_verified", "updated_at"])
        return instance


class PhoneOTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class PhoneOTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)


class VerificationStatusSerializer(serializers.Serializer):
    membership_number = serializers.CharField()
    is_verified = serializers.BooleanField()
    phone_verified = serializers.BooleanField()
    kyc_complete = serializers.BooleanField()
    next_of_kin_added = serializers.BooleanField()
    submitted = serializers.BooleanField()

    def to_representation(self, instance):
        return {
            "membership_number": instance.membership_number,
            **instance.verification_status(),
        }
