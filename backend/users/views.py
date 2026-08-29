import os

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import UserAccessPermission
from .models import EmailVerificationCode, Notification
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    EmailVerificationRequestSerializer,
    EmailVerificationVerifySerializer,
    NotificationSerializer,
    PasswordResetSerializer,
    PasswordResetTRequestSerializer,
    PinLoginSerializer,
    PinSetupConfirmSerializer,
    PinSetupRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    """JWT login, rate limited so credentials cannot be brute-forced.

    Refuses to issue tokens until the account's email is verified.
    """

    throttle_scope = "auth"
    serializer_class = CustomTokenObtainPairSerializer


class UserViewList(viewsets.ModelViewSet):
    """Staff user accounts.

    Member (role ME) login accounts are deliberately excluded here: those
    people are managed as *members* in the Members module, not as system users.
    """
    queryset = User.objects.exclude(role=User.MEMBER)
    serializer_class = UserSerializer
    permission_classes = [UserAccessPermission]


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """Authenticated user's profile, without exposing another user's record."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class RegisterView(generics.CreateAPIView):
    """
    Public self-service registration for members.

    Fields:
        - first_name
        - last_name
        - phone_number
        - email
        - password
        - confirm_password

    Creates a login account (role = Member) and an unverified Member profile.
    """
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    throttle_scope = "auth"


class LogoutView(APIView):
    """
    Logout. Local token removal is the source of truth in the frontend; this
    endpoint deliberately requires no authentication and always succeeds so a
    logout can never fail or bounce the user back into a refresh loop.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK)

    def get(self, request):
        return self.post(request)


class EmailVerificationRequestView(APIView):
    """
    (Re)send a 6-digit email verification code.

    Public: used right after registration and from the login screen when the
    email is not yet verified. Non-existent addresses get a generic success so
    we never disclose which emails are registered.
    """
    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationRequestSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        user = User.objects.filter(email=email).first()
        if user is not None and user.email_verified:
            return Response(
                {
                    "message": "This email is already verified. You can log in now.",
                    "already_verified": True,
                },
                status=status.HTTP_200_OK,
            )

        if user is None:
            # Generic response: do not reveal whether the account exists.
            return Response(
                {"message": "Verification code sent.", "already_verified": False},
                status=status.HTTP_200_OK,
            )

        from django.conf import settings
        from .services import issue_email_code

        code_obj = issue_email_code(user)
        payload = {
            "message": "Verification code sent.",
            "expires_in_minutes": EmailVerificationCode.TTL_MINUTES,
            "already_verified": False,
            "email_sent": getattr(code_obj, "email_sent", False),
        }
        # Surface SMTP failures so the frontend (and support) can see exactly
        # why an email did not arrive instead of the user waiting forever.
        if not payload["email_sent"]:
            payload["email_error"] = getattr(code_obj, "email_error", "Unknown mail error.")
        # Console backend (no real SMTP) = dev/demo mode: return the code so
        # local testing and the demo can complete email verification easily.
        if settings.EMAIL_DEV_MODE:
            payload["dev_code"] = code_obj.code
        return Response(payload, status=status.HTTP_200_OK)


class EmailVerificationVerifyView(APIView):
    """
    Confirm the email address using the 6-digit code.

    Marks the account as email-verified once the correct, still-valid code is
    supplied (max 5 attempts, code is single use and expires after 30 minutes).
    """
    permission_classes = (AllowAny,)
    serializer_class = EmailVerificationVerifySerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"]

        user = User.objects.filter(email=email).first()
        if user is None:
            return Response(
                {"message": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.email_verified:
            return Response(
                {"message": "Email already verified.", "already_verified": True},
                status=status.HTTP_200_OK,
            )

        from .services import verify_email_code
        if not verify_email_code(user, code):
            return Response(
                {"message": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Email verified. You can log in now."},
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestView(generics.GenericAPIView):
    """
    Request password reset for a user. Send an email with a reset link containing a token and uid. \n
    Fields:
        - email
    """
    permission_classes = (AllowAny,)
    serializer_class = PasswordResetTRequestSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get('email')

        user = User.objects.filter(email=email).first()
        if not user:
            # Do not reveal whether an account exists for a given email.
            return Response(
                {"message": "Password reset email sent successfully"},
                status=status.HTTP_200_OK,
            )

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

        reset_url = f"{frontend_url}/reset-password/?user={uid}&token={token}"

        from .emails import send_password_reset_email
        sent, error = send_password_reset_email(user, reset_url)
        payload = {"message": "Password reset email sent successfully"}
        # Surface SMTP failures (e.g. missing/incorrect credentials) so support
        # can see why the email never arrived instead of the user waiting.
        if not sent:
            payload["email_sent"] = False
            payload["email_error"] = error or "Unknown mail error."
        return Response(payload, status=status.HTTP_200_OK)


class PasswordResetView(generics.GenericAPIView):
    """
    Password reset view to handle password reset requests. Validate the token and uid, and set the new password. \n
    Fields:
    - uid
    - token
    - password
    """
    serializer_class = PasswordResetSerializer
    permission_classes = (AllowAny,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        try:
            uid = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.filter(pk=uid).first()
        except (TypeError, ValueError, OverflowError):
            user = None

        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {"message": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save()

        return Response(
            {"message": "Password reset successful"},
            status=status.HTTP_204_NO_CONTENT
        )


class ChangePasswordView(generics.GenericAPIView):
    """Change the authenticated user's password after verifying the current one."""

    permission_classes = (IsAuthenticated,)
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()

        return Response(
            {"message": "Password changed successfully"},
            status=status.HTTP_200_OK,
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """The authenticated user's in-app notifications."""

    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="read")
    def mark_read(self, request):
        notification_id = request.data.get("notification_id")
        queryset = self.get_queryset()
        if notification_id:
            queryset.filter(pk=notification_id).update(is_read=True)
        else:
            queryset.update(is_read=True)
        return Response({"detail": "Notifications marked as read."}, status=status.HTTP_200_OK)


class PinSetupRequestView(APIView):
    """
    Step 1 of quick-login PIN setup: the user types their phone number and we
    email a 6-digit confirmation code to the account on file (the phone number
    identifies the account, the emailed code proves ownership).

    Non-existent numbers get a generic success so we never disclose which
    phones are registered.
    """
    permission_classes = (AllowAny,)
    throttle_scope = "auth"

    def post(self, request):
        serializer = PinSetupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        from django.conf import settings
        from .models import PinSetupCode
        from .services import issue_pin_setup_code, user_by_phone

        user = user_by_phone(phone_number)
        if user is None:
            return Response(
                {
                    "message": (
                        "If that number belongs to a member, a confirmation code "
                        "is on its way to their email."
                    ),
                    "already_set": False,
                },
                status=status.HTTP_200_OK,
            )

        code_obj = issue_pin_setup_code(user)
        payload = {
            "message": "Confirmation code sent.",
            "expires_in_minutes": PinSetupCode.TTL_MINUTES,
            "already_set": user.has_pin,
            "email_sent": getattr(code_obj, "email_sent", False),
        }
        if not payload["email_sent"]:
            payload["email_error"] = getattr(code_obj, "email_error", "Unknown mail error.")
        if settings.EMAIL_DEV_MODE:
            payload["dev_code"] = code_obj.code
        return Response(payload, status=status.HTTP_200_OK)


class PinSetupConfirmView(APIView):
    """
    Step 2 of PIN setup: validate the emailed code and store the 4-digit PIN.
    A correct code also marks the email verified (the user clearly read it).
    """
    permission_classes = (AllowAny,)
    serializer_class = PinSetupConfirmSerializer
    throttle_scope = "auth"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]
        pin = serializer.validated_data["pin"]

        from .services import user_by_phone, verify_pin_setup_code

        user = user_by_phone(phone_number)
        if user is None or not verify_pin_setup_code(user, code):
            return Response(
                {"detail": "Invalid or expired confirmation code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_pin(pin)
        user.email_verified = True
        user.save(update_fields=["pin_hash", "pin_attempts", "pin_locked_until", "email_verified"])
        return Response(
            {
                "message": "Secret PIN set. You can now log in with your phone number and PIN.",
                "success": True,
            },
            status=status.HTTP_200_OK,
        )


class PinLoginView(APIView):
    """
    Quick login on the phone/PWA: phone number + 4-digit PIN instead of the
    long password. Wrong PINs are counted and the PIN locks after a few tries.

    JWT tokens returned are the same format as a normal password login.
    """
    permission_classes = (AllowAny,)
    serializer_class = PinLoginSerializer
    throttle_scope = "pin"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        pin = serializer.validated_data["pin"]

        from .models import User
        from .services import user_by_phone, verify_pin

        user = user_by_phone(phone_number)
        if user is None or not user.is_active:
            return Response(
                {"detail": "No active member is registered with that phone number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.role != User.MEMBER or not user.email_verified:
            return Response(
                {
                    "detail": (
                        "Your email address isn't verified yet. "
                        "Verify it with the emailed code to enable quick login."
                    ),
                    "email_not_verified": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.has_pin:
            return Response(
                {
                    "detail": (
                        "No secret PIN is set for this account yet. "
                        "Set it up once and you'll jump straight to your dashboard."
                    ),
                    "pin_not_set": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        status_result, locked_seconds = verify_pin(user, pin)
        if status_result == "locked":
            return Response(
                {
                    "detail": (
                        "Too many wrong attempts. The quick-login PIN is locked "
                        f"for about {max(1, locked_seconds // 60)} minutes."
                    ),
                    "pin_locked": True,
                    "locked_seconds": locked_seconds,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if status_result == "invalid":
            remaining = max(0, user.__class__.PIN_MAX_ATTEMPTS - user.pin_attempts)
            return Response(
                {
                    "detail": f"Wrong PIN. {remaining} attempt(s) left before it locks.",
                    "pin_invalid": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
