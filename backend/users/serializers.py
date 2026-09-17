from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.validators import UniqueValidator

# from .models import Profile
from .models import Notification
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "profile_image", "username"]
        read_only_fields = ["role"]

# class UserProfileSerializer(serializers.ModelSerializer):
#     role_display = serializers.SerializerMethodField()

#     class Meta:
#         model = Profile
#         fields = ['role_display', 'profile_image']

#     def get_role_display(self, obj):
#         return obj.get_role_display()


# class UserSerializer(serializers.HyperlinkedModelSerializer):
#     profile = UserProfileSerializer()

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'profile']

#     def create(self, validated_data):
#         profile = validated_data.pop('profile')
#         return User.objects.create(profile=Profile.objects.create(**profile), **validated_data)

#     def update(self, instance, validated_data):
#         instance.username = validated_data.get("username", instance.username)
#         instance.email = validated_data.get("email", instance.email)
#         instance.save()

#         if "profile" in validated_data:
#             instance.profile.profile_image = validated_data["profile"].get(
#                 "profile_image", instance.profile.profile_image)
#             instance.profile.role = validated_data["profile"].get(
#                 "role", instance.profile.role)
#             instance.profile.save()
#         return instance


class EmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerificationVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login serializer that refuses access until the email is verified.

    Self-registered members receive a 6-digit code on registration; until they
    confirm it they can re-request the code but cannot obtain tokens.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        # Only self-registered members go through the email code flow; staff
        # accounts (created by admins) are not blocked by the flag.
        if user.role == User.MEMBER and not user.email_verified:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Email not verified. Enter the 6-digit code we emailed you "
                        "to confirm your address and log in."
                    ),
                    "email_not_verified": True,
                },
                code="email_not_verified",
            )
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """
    Public self-service registration for members.

    Creates a login account (role = Member) plus an unverified Member profile.
    Verification is completed afterwards via phone OTP, KYC uploads and next of
    kin — until then the member cannot create groups or borrow.
    """
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=20, write_only=True)
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'password',
            'confirm_password',
        )

    def _strong_password(self, pw, email):
        import re
        if len(pw) < 10:
            raise serializers.ValidationError({"password": "Password must be at least 10 characters."})
        if not re.search(r"[A-Z]", pw):
            raise serializers.ValidationError({"password": "Password must include at least one capital letter."})
        if len(re.findall(r"[a-z]", pw)) < 3:
            raise serializers.ValidationError({"password": "Password must include at least three lowercase letters."})
        if not re.search(r"[0-9]", pw):
            raise serializers.ValidationError({"password": "Password must include at least one number."})
        if len(re.findall(r"[^A-Za-z0-9]", pw)) < 2:
            raise serializers.ValidationError({"password": "Password must include at least two symbols (e.g. @ # $ % & *)."})
        if email and pw.lower() == email.lower():
            raise serializers.ValidationError({"password": "Password must not be the same as email."})
        if email and email.split("@")[0].lower() in pw.lower():
            raise serializers.ValidationError({"password": "Password must not contain your email name."})

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."})
        self._strong_password(attrs['password'], attrs.get('email', ''))
        return attrs

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists.")
        return email

    def validate_phone_number(self, value):
        import re
        if not re.match(r"^\+255[67]\d{8}$", value):
            raise serializers.ValidationError(
                "Tanzania numbers only. Use +255 followed by 9 digits starting with 6 or 7 (e.g. +255712345678).")
        from members.models import Member
        if Member.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "This phone number is already registered to a member.")
        return value

    def create(self, validated_data):
        from members.models import Member
        confirm_password = validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        phone_number = validated_data.pop("phone_number")
        email = validated_data.pop("email").strip().lower()

        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                username=email,
                first_name=validated_data.pop("first_name"),
                last_name=validated_data.pop("last_name"),
                role=User.MEMBER,
            )
            Member.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                phone_number=phone_number,
                email=user.email,
                registration_source=Member.RegistrationSource.SELF,
            )

        # Issue + send the email verification code right away (dev/demo mode
        # prints it to the console via the backend fallback).
        from .services import issue_email_code
        issue_email_code(user)
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        member = getattr(instance, "member", None)
        if member is None:
            data["member"] = None
            return data
        data["member"] = {
            "membership_number": member.membership_number,
            "is_verified": member.is_verified,
            "phone_verified": member.phone_verified,
            "status": member.status,
        }
        return data


class PasswordResetTRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(
        min_length=8,
        validators=[validate_password],
        write_only=True
    )


def _validate_pin(value):
    if not (len(value) == 4 and value.isdigit()):
        raise serializers.ValidationError(
            "The secret PIN must be exactly 4 digits.")
    return value


class PinSetupRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class PinSetupConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)
    pin = serializers.CharField(max_length=4, validators=[_validate_pin], write_only=True)


class PinLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    pin = serializers.CharField(max_length=4, validators=[_validate_pin], write_only=True)


class NotificationSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "title", "body", "kind", "kind_display", "link", "is_read", "created_at"]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        min_length=8,
        validators=[validate_password],
        write_only=True,
    )

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


# class ProfileSerializer(serializers.ModelSerializer):
#     user = UserSerializer()
#     role_display = serializers.SerializerMethodField()

#     class Meta:
#         model = Profile
#         fields = ('user', 'role_display', 'profile_image')

#     def get_role_display(self, obj):
#         return obj.get_role_display()
