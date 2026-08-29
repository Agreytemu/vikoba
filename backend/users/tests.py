from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import SavingsProduct
from customers.models import Customer
from loans.models import LoanProduct
from members.models import Member
from .models import PinSetupCode, User

# A single test process shares one throttle bucket keyed by scope + client IP.
# The whole users suite makes far more than 30 auth-scoped requests in under a
# minute, so these classes bump the limits to avoid spurious 429s (which none
# of the tests assert on).
HIGH_THROTTLE_RATES = {
    "anon": "10000/min",
    "auth": "10000/min",
    "pin": "10000/min",
}


class RegisteredMemberMixin:
    """Registers a self-service member and (optionally) verifies the email."""

    def set_up_member(self, email="pin.member@example.com", phone="+254700555666"):
        payload = {
            "first_name": "Pia",
            "last_name": "Ngoma",
            "phone_number": phone,
            "email": email,
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        }
        response = self.client.post("/api/v1/auth/register", payload, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=email)
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        return user


@override_settings(DEFAULT_THROTTLE_RATES=HIGH_THROTTLE_RATES)
class PasswordResetTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unknown_email_receives_generic_response(self):
        response = self.client.post(
            "/api/v1/auth/request-password-reset",
            {"email": "ghost@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.data)

    def test_known_email_sends_a_real_reset_email(self):
        User.objects.create_user(
            email="reset.me@example.com",
            username="reset-me",
            password="test-password-123",
        )
        mail.outbox.clear()

        response = self.client.post(
            "/api/v1/auth/request-password-reset",
            {"email": "reset.me@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Reset your", message.subject)
        self.assertIn("/reset-password/", message.body)


@override_settings(DEFAULT_THROTTLE_RATES=HIGH_THROTTLE_RATES)
class PinSetupAndLoginTest(TestCase, RegisteredMemberMixin):
    def setUp(self):
        self.client = APIClient()
        self.user = self.set_up_member()
        self.phone = "+254700555666"

    def send_pin_code(self):
        return self.client.post(
            "/api/v1/auth/pin/setup-request", {"phone_number": self.phone}, format="json"
        )

    def test_pin_setup_request_emails_code(self):
        mail.outbox.clear()
        response = self.send_pin_code()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PinSetupCode.objects.filter(user=self.user).exists())
        if response.data.get("email_sent", True):
            self.assertEqual(len(mail.outbox), 1)

    def test_pin_setup_confirm_sets_pin_and_verifies_email(self):
        code = "135790"
        PinSetupCode.objects.create(
            user=self.user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=PinSetupCode.TTL_MINUTES),
        )

        response = self.client.post(
            "/api/v1/auth/pin/setup-confirm",
            {"phone_number": self.phone, "code": code, "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_pin)
        self.assertTrue(self.user.email_verified)

    def test_pin_login_with_correct_pin_returns_tokens(self):
        self.user.set_pin("2468")
        self.user.save(update_fields=["pin_hash"])

        response = self.client.post(
            "/api/v1/auth/pin/login",
            {"phone_number": self.phone, "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_wrong_pin_counts_attempts_and_locks(self):
        self.user.set_pin("2468")
        self.user.save(update_fields=["pin_hash"])

        for i in range(User.PIN_MAX_ATTEMPTS - 1):
            response = self.client.post(
                "/api/v1/auth/pin/login",
                {"phone_number": self.phone, "pin": "0000"},
                format="json",
            )
            self.assertEqual(response.status_code, 400, f"attempt {i + 1}")
            self.assertTrue(response.data.get("pin_invalid"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.pin_attempts, User.PIN_MAX_ATTEMPTS - 1)

        # The final wrong attempt locks the PIN.
        response = self.client.post(
            "/api/v1/auth/pin/login",
            {"phone_number": self.phone, "pin": "0000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data.get("pin_locked"))
        self.assertGreaterEqual(response.data.get("locked_seconds", 0), 60)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_pin_locked)

    def test_pin_login_requires_email_verified(self):
        self.user.email_verified = False
        self.user.set_pin("2468")
        self.user.save(update_fields=["email_verified", "pin_hash"])

        response = self.client.post(
            "/api/v1/auth/pin/login",
            {"phone_number": self.phone, "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data.get("email_not_verified"))

    def test_pin_login_unknown_phone_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/pin/login",
            {"phone_number": "+255000000000", "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_pin_login_without_a_pin_set_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/pin/login",
            {"phone_number": self.phone, "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data.get("pin_not_set"))

    def test_pin_must_be_exactly_four_digits(self):
        response = self.client.post(
            "/api/v1/auth/pin/setup-confirm",
            {"phone_number": self.phone, "code": "123456", "pin": "12"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_pin_code(self):
        response = self.client.post(
            "/api/v1/auth/pin/setup-confirm",
            {"phone_number": self.phone, "code": "999999", "pin": "2468"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_pin)


class LogoutTest(TestCase):
    def test_logout_succeeds_even_unauthenticated(self):
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/logout").status_code, 200)


class SeedDataCommandTest(TestCase):
    def test_seed_demo_data_creates_sample_records(self):
        call_command("seed_demo_data", verbosity=0)

        self.assertTrue(User.objects.filter(email="admin@example.com").exists())
        self.assertTrue(Member.objects.exists())
        self.assertTrue(Customer.objects.exists())
        self.assertTrue(SavingsProduct.objects.exists())
        self.assertTrue(LoanProduct.objects.exists())


class ChangePasswordViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="password@example.com",
            username="password-user",
            password="old-password-123",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_change_password_requires_current_password_and_updates_password(self):
        response = self.client.post(
            "/api/v1/auth/change-password",
            {"current_password": "old-password-123", "new_password": "new-password-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-password-123"))


class RoleAccessControlAPITest(TestCase):
    """The API policy is the source of truth; the UI only mirrors this policy."""

    def setUp(self):
        self.client = APIClient()
        self.users = {
            role: User.objects.create_user(
                email=f"{role.lower()}@example.com",
                username=role.lower(),
                password="test-password-123",
                role=role,
            )
            for role in (
                User.ADMIN,
                User.MANAGER,
                User.OPERATION,
                User.FINANCE,
                User.LOAN,
                User.ACCOUNTANT,
            )
        }

    def get_as(self, role, url):
        self.client.force_authenticate(self.users[role])
        return self.client.get(url)

    def test_module_reads_follow_the_role_matrix(self):
        module_urls = {
            "/api/v1/members/": {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.LOAN, User.ACCOUNTANT},
            "/api/v1/accounts/": {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.LOAN, User.ACCOUNTANT},
            "/api/v1/transactions/": {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.LOAN, User.ACCOUNTANT},
            "/api/v1/products/": {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.LOAN, User.ACCOUNTANT},
            "/api/v1/loans/": {User.ADMIN, User.MANAGER, User.OPERATION, User.LOAN},
            "/api/v1/auth/users/": {User.ADMIN, User.MANAGER},
        }

        for url, allowed_roles in module_urls.items():
            for role in self.users:
                with self.subTest(url=url, role=role):
                    response = self.get_as(role, url)
                    self.assertEqual(response.status_code, 200 if role in allowed_roles else 403)

    def test_only_admins_and_managers_can_create_account_products(self):
        payload = {
            "name": "Junior Savings",
            "code": "JNR",
            "minimum_balance": "100.00",
            "interest_rate": "2.50",
            "withdrawal_fee": "0.00",
            "allows_withdrawals": True,
            "is_active": True,
        }

        for role in self.users:
            with self.subTest(role=role):
                self.client.force_authenticate(self.users[role])
                response = self.client.post("/api/v1/products/", payload, format="json")
                expected = 201 if role in {User.ADMIN, User.MANAGER} else 403
                self.assertEqual(response.status_code, expected)

                if response.status_code == 201:
                    payload["code"] = f"JNR-{role}"
                    payload["name"] = f"Junior Savings {role}"

    def test_anyone_can_self_register_as_an_unverified_member(self):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone_number": "+254700111222",
            "email": "jane.doe@example.com",
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        }

        response = self.client.post("/api/v1/auth/register", payload, format="json")
        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email="jane.doe@example.com")
        self.assertEqual(user.role, User.MEMBER)

        member = user.member
        self.assertIsNotNone(member)
        self.assertFalse(member.is_verified)
        self.assertFalse(member.phone_verified)
        self.assertEqual(member.phone_number, "+254700111222")
        self.assertEqual(member.registration_source, Member.RegistrationSource.SELF)

    def test_self_registration_rejects_duplicate_phone(self):
        payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "phone_number": "+254700111222",
            "email": "jane.doe@example.com",
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        }
        self.assertEqual(
            self.client.post("/api/v1/auth/register", payload, format="json").status_code,
            201,
        )

        payload["email"] = "other@example.com"
        self.assertEqual(
            self.client.post("/api/v1/auth/register", payload, format="json").status_code,
            400,
        )

    def test_current_user_endpoint_only_returns_the_authenticated_user(self):
        self.client.force_authenticate(self.users[User.ACCOUNTANT])
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.users[User.ACCOUNTANT].id)


@override_settings(DEFAULT_THROTTLE_RATES=HIGH_THROTTLE_RATES)
class EmailVerificationTest(TestCase):
    """Self-registered members must verify their email before they can log in."""

    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "first_name": "Daniel",
            "last_name": "Kim",
            "phone_number": "+254700555666",
            "email": "daniel.kim@example.com",
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        }

    def register(self):
        return self.client.post("/api/v1/auth/register", self.payload, format="json")

    def test_registration_issues_an_email_verification_code(self):
        self.assertEqual(self.register().status_code, 201)
        user = User.objects.get(email=self.payload["email"])
        self.assertFalse(user.email_verified)
        self.assertTrue(user.email_verification_codes.exists())

    def test_login_is_blocked_until_email_verified(self):
        self.register()
        user = User.objects.get(email=self.payload["email"])

        login = self.client.post(
            "/api/v1/auth/login",
            {"email": self.payload["email"], "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 400)
        self.assertTrue(login.data.get("email_not_verified"))

        code = user.email_verification_codes.order_by("-created_at", "-pk").first().code
        verify = self.client.post(
            "/api/v1/auth/email-verify",
            {"email": self.payload["email"], "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

        login = self.client.post(
            "/api/v1/auth/login",
            {"email": self.payload["email"], "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)

    def test_wrong_code_does_not_verify_email(self):
        self.register()
        user = User.objects.get(email=self.payload["email"])

        self.assertEqual(
            self.client.post(
                "/api/v1/auth/email-verify",
                {"email": self.payload["email"], "code": "000000"},
                format="json",
            ).status_code,
            400,
        )
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_expired_code_cannot_be_used(self):
        self.register()
        user = User.objects.get(email=self.payload["email"])
        code_obj = user.email_verification_codes.order_by("-created_at", "-pk").first()
        code_obj.expires_at = timezone.now() - timedelta(minutes=1)
        code_obj.save(update_fields=["expires_at"])

        response = self.client.post(
            "/api/v1/auth/email-verify",
            {"email": self.payload["email"], "code": code_obj.code},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_resend_request_rotates_the_code(self):
        self.register()
        user = User.objects.get(email=self.payload["email"])
        first = user.email_verification_codes.order_by("-created_at", "-pk").first()

        response = self.client.post(
            "/api/v1/auth/email-verify-request",
            {"email": self.payload["email"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        second = user.email_verification_codes.order_by("-created_at", "-pk").first()
        self.assertNotEqual(first.code, second.code)
        first.refresh_from_db()
        self.assertTrue(first.is_used)

    def test_staff_accounts_can_login_without_email_code(self):
        # Staff are created by admins and never go through the email code flow.
        User.objects.create_user(
            email="staff.login@example.com",
            username="staff-login",
            password="test-password-123",
            role=User.ACCOUNTANT,
        )
        login = self.client.post(
            "/api/v1/auth/login",
            {"email": "staff.login@example.com", "password": "test-password-123"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)
