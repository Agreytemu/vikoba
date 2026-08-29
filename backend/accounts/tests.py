from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from members.models import Member
from users.models import User

from .models import SavingsAccount, SavingsProduct


class WalletAPITest(TestCase):
    """Member self-service wallet: deposits (open) and withdrawals (verified only)."""

    def setUp(self):
        self.client = APIClient()
        self.product = SavingsProduct.objects.create(
            name="Ordinary Savings",
            code="OS",
            minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"),
            withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )
        self.member = self._member(
            "member@example.com", "+254700000001", verified=True
        )
        self.unverified = self._member(
            "unverified@example.com", "+254700000002", verified=False
        )
        self.account = SavingsAccount.objects.create(
            member=self.member,
            product=self.product,
            balance=Decimal("50000.00"),
        )
        self.unverified_account = SavingsAccount.objects.create(
            member=self.unverified,
            product=self.product,
            balance=Decimal("0.00"),
        )

    def _member(self, email, phone, verified):
        user = User.objects.create_user(
            email=email,
            username=email.split("@")[0],
            password="test-password-123",
            role=User.MEMBER,
            email_verified=verified,
        )
        return Member.objects.create(
            user=user,
            first_name=email.split("@")[0].title(),
            last_name="Test",
            phone_number=phone,
            email=email,
            registration_source=Member.RegistrationSource.ADMIN,
            is_verified=verified,
        )

    def force(self, user):
        self.client.force_authenticate(user)

    def test_any_member_can_request_a_deposit(self):
        self.force(self.unverified.user)
        response = self.client.post(
            "/api/v1/accounts/me/deposits/",
            {"amount": "1000.00", "channel": "MPESA"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/api/v1/accounts/me/deposits/",
            {"amount": "1000.00", "account_number": self.unverified_account.account_number, "channel": "mpesa"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("reference", response.data)

    def test_withdrawal_requires_verification(self):
        self.force(self.unverified.user)
        response = self.client.post(
            "/api/v1/accounts/me/withdrawals/",
            {"amount": "500.00", "account_number": self.unverified_account.account_number},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.data.get("verification_required"))

    def test_verified_member_can_request_a_withdrawal(self):
        self.force(self.member.user)
        response = self.client.post(
            "/api/v1/accounts/me/withdrawals/",
            {"amount": "500.00", "account_number": self.account.account_number},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("reference", response.data)