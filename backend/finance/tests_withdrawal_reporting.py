"""Phase 5 STEP 8: ledger-derived withdrawal report tests.

A withdrawal only reports ``paid_out`` once its WITHDRAWAL journal posting
exists (never from request status alone). Covered:
- success request with ledger posting → paid out
- success/approved request without a ledger posting → surfaced gap
- member-scoped and status filters narrow the report
- only business-role staff may view
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct, WithdrawalRequest
from finance.models import FinancialTransaction
from finance.services.accounts_catalog import get_or_create_member_savings_account
from finance.services.engine import post_transaction
from members.models import Member

User = get_user_model()


class WithdrawalReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="wrep1@test.com", username="wrep1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MWRP01",
            first_name="With",
            last_name="Member",
            phone_number="+255712000501",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.ms = get_or_create_member_savings_account(self.account)
        self.staff = User.objects.create_user(
            email="wrepfin@test.com", username="wrepfin", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)

    def _request(self, amount="3000.00", status="SUCCESS", ref=None):
        return WithdrawalRequest.objects.create(
            member=self.member,
            account=self.account,
            amount=Decimal(amount),
            status=status,
            reference=ref or f"WDR-{WithdrawalRequest.objects.count() + 1}",
        )

    def _pay_out(self, wdrm, key):
        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.WITHDRAWAL,
            amount=wdrm.amount,
            entries=[
                {"account": self.ms, "entry_type": "DEBIT", "amount": wdrm.amount},
                {"account": get_org_clearing(), "entry_type": "CREDIT", "amount": wdrm.amount},
            ],
            member=self.member,
            withdrawal_request=wdrm,
            reference=f"WDR-P-{key}",
        )

    def test_paid_withdrawal_reports_journal(self):
        wdrm = self._request(amount="3000.00")
        self._pay_out(wdrm, "1")
        resp = self.staff_client.get("/api/v1/finance/reports/withdrawals/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "withdrawals")
        self.assertEqual(body["summary"]["requests"], 1)
        self.assertEqual(body["summary"]["paid_out"], "3000.00")
        self.assertEqual(body["summary"]["unrecorded_in_ledger"], 0)
        self.assertTrue(body["rows"][0]["paid_out"])
        self.assertEqual(body["rows"][0]["ledger"]["amount"], "3000.00")

    def test_success_without_ledger_is_a_gap(self):
        self._request(status="SUCCESS", ref="WDR-NO-LEDGER")
        resp = self.staff_client.get("/api/v1/finance/reports/withdrawals/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["summary"]["paid_out"], "0.00")
        self.assertEqual(body["summary"]["unrecorded_in_ledger"], 1)
        self.assertFalse(body["rows"][0]["paid_out"])
        self.assertIsNone(body["rows"][0]["ledger"])

    def test_status_filter_narrows_report(self):
        pending = self._request(status="PENDING", ref="WDR-PENDING")
        self._request(status="SUCCESS", ref="WDR-SUCCESS")
        resp = self.staff_client.get(
            "/api/v1/finance/reports/withdrawals/?status=PENDING"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["summary"]["requests"], 1)
        self.assertEqual(body["rows"][0]["reference"], "WDR-PENDING")

    def test_member_blocked_from_staff_report(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.get("/api/v1/finance/reports/withdrawals/")
        self.assertEqual(resp.status_code, 403)


def get_org_clearing():
    from finance.services.accounts_catalog import get_org_account

    return get_org_account("1100-CLEARING")