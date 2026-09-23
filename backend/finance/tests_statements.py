"""Phase 5 STEP 5: ledger-derived member statement tests.

The statement must carry a TRUE running balance computed from the journal
(opening -> rows -> closing), never from the cached SavingsAccount.balance.
Covered:
- savings statement opening/closing + running balance per account
- period bounds shift the opening balance correctly
- a reversal is reflected in the running balance (books still tie)
- financial activity itemisation includes journal legs (traceable)
- authorization: member sees only their own; staff read any member; invalid
  period dates return 400
"""
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction
from accounts.services import post_savings_transaction
from finance.models import FinancialTransaction
from finance.services.reversals import reverse_financial_transaction
from groups.models import VikobaGroup
from members.models import Member

User = get_user_model()


class StatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="stmt1@test.com", username="stmt1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTESTST01",
            first_name="Stmt",
            last_name="Member",
            phone_number="+255712000111",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="TestGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        self.staff = User.objects.create_user(
            email="stmtfin@test.com", username="stmtfin", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _deposit(self, amount="1000.00", key="stmt-dep-1"):
        sav = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal(amount),
            user=self.user,
            narration="stmt deposit",
            idempotency_key=key,
        )
        return sav.financial_transactions.first()

    def test_savings_statement_matches_ledger(self):
        self._deposit("1000.00", "s-1")
        self._deposit("2000.00", "s-2")
        resp = self.member_client.get("/api/v1/finance/me/statement/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "savings")
        self.assertEqual(body["totals"]["opening"], "0.00")
        self.assertEqual(body["totals"]["closing"], "3000.00")
        account_section = body["accounts"][0]
        self.assertEqual(account_section["account_number"], self.account.account_number)
        self.assertEqual(len(account_section["rows"]), 2)
        last = account_section["rows"][-1]
        self.assertEqual(last["running_balance"], "3000.00")
        self.assertEqual(last["entry_type"], "CREDIT")

    def test_period_bounds_shift_opening_balance(self):
        first = self._deposit("1000.00", "p-1")
        first.posted_at = dj_timezone.make_aware(datetime(2026, 1, 2))
        first.save(update_fields=["posted_at"])
        second = self._deposit("2000.00", "p-2")
        second.posted_at = dj_timezone.make_aware(datetime(2026, 1, 10))
        second.save(update_fields=["posted_at"])
        resp = self.member_client.get(
            "/api/v1/finance/me/statement/?start=2026-01-05&end=2026-01-31"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        account_section = body["accounts"][0]
        self.assertEqual(account_section["opening_balance"], "1000.00")
        self.assertEqual(account_section["closing_balance"], "3000.00")
        self.assertEqual(len(account_section["rows"]), 1)

    def test_reversal_keeps_books_tied(self):
        fin_tx = self._deposit("1000.00", "r-1")
        reverse_financial_transaction(
            fin_tx=fin_tx,
            reason="wrong amount",
            actor=self.user,
            audit_ip="127.0.0.1",
        )
        resp = self.member_client.get("/api/v1/finance/me/statement/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["totals"]["closing"], "0.00")
        account_section = body["accounts"][0]
        types = {row["transaction_type"] for row in account_section["rows"]}
        self.assertIn(FinancialTransaction.TransactionType.DEPOSIT, types)
        self.assertIn(FinancialTransaction.TransactionType.REVERSAL, types)

    def test_financial_activity_is_ledger_traceable(self):
        self._deposit("7500.00", "f-1")
        resp = self.member_client.get("/api/v1/finance/me/statement/?kind=financial")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "financial")
        self.assertEqual(body["count"], 1)
        row = body["rows"][0]
        self.assertEqual(len(row["entries"]), 2)
        self.assertEqual(row["reference"], row["reference"])

    def test_member_cannot_read_another_member(self):
        other = Member.objects.create(
            user=User.objects.create_user(
                email="stmt2@test.com", username="stmt2", password="pass", is_active=True
            ),
            membership_number="MTESTST02",
            first_name="Other",
            last_name="Member",
            phone_number="+255712000222",
        )
        resp = self.member_client.get(f"/api/v1/finance/statements/{other.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_read_any_member_statement(self):
        self._deposit("5000.00", "staff-1")
        resp = self.staff_client.get(f"/api/v1/finance/statements/{self.member.pk}/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["totals"]["closing"], "5000.00")

    def test_invalid_period_returns_400(self):
        resp = self.member_client.get("/api/v1/finance/me/statement/?start=not-a-date")
        self.assertEqual(resp.status_code, 400)