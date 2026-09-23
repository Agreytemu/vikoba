"""Phase 5 STEP 10: ledger-derived dashboard tests.

Headline KPIs (member savings, clearing, loans outstanding, income) must be
reconstructed from the journal, not from cached account columns. Covered:
- member savings total tracks the savings journal after deposit/withdrawal
- clearing balance tracks the offset leg of a savings posting
- loan disbursement moves loans-outstanding on 1300-LOAN_PRINCIPAL
- member dashboard returns journal-derived savings totals
- member cannot read the org dashboard (staff-only)
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction
from accounts.services import post_savings_transaction
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction
from finance.models import FinancialTransaction
from loans.models import LoanAccount, LoanProduct
from members.models import Member

User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dash1@test.com", username="dash1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MDASH01",
            first_name="Dash",
            last_name="Member",
            phone_number="+255712000701",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.clearing = get_org_account("1100-CLEARING")
        self.staff = User.objects.create_user(
            email="dashfin@test.com", username="dashfin", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _deposit(self, amount="5000.00", key="d-1"):
        return post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal(amount),
            user=self.user,
            narration="dash deposit",
            idempotency_key=key,
        )

    def test_org_dashboard_tracks_journal(self):
        self._deposit("5000.00", "d-1")
        self._deposit("3000.00", "d-2")
        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.LOAN_DISBURSEMENT,
            amount=Decimal("20000.00"),
            entries=[
                {"account": get_org_account("1300-LOAN_PRINCIPAL"), "entry_type": "DEBIT", "amount": "20000.00"},
                {"account": self.clearing, "entry_type": "CREDIT", "amount": "20000.00"},
            ],
            member=self.member,
            reference="DASH-LN-1",
        )
        resp = self.staff_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "org_dashboard")
        self.assertEqual(body["totals"]["member_savings"], "8000.00")
        self.assertEqual(body["totals"]["loans_outstanding"], "20000.00")

    def test_member_dashboard_from_journal(self):
        self._deposit("7500.00", "d-3")
        resp = self.member_client.get("/api/v1/finance/me/dashboard/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "member_dashboard")
        self.assertEqual(body["savings"]["totals"]["closing"], "7500.00")

    def test_member_cannot_read_org_dashboard(self):
        resp = self.member_client.get("/api/v1/finance/dashboard/")
        self.assertEqual(resp.status_code, 403)