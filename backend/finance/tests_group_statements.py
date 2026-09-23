"""Phase 5 STEP 6: ledger-derived group statement tests.

The group statement must be journal-backed (never the in-memory fusion used by
``/ledger``):
- deposits move the running balance up, withdrawals down (member-savings legs)
- period bounds shift the opening balance and filter rows
- a loan disbursement (no member-savings leg) shows delta 0 yet is counted in
  flow_totals — nothing is report-only
- authorization: only active group members may read it
"""
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct
from accounts.services import post_savings_transaction
from finance.models import FinancialTransaction
from finance.services.accounts_catalog import (
    get_org_account,
    get_or_create_group_cash_account,
    get_or_create_member_savings_account,
)
from finance.services.engine import post_transaction
from groups.models import GroupMembership, VikobaGroup
from members.models import Member

User = get_user_model()


class GroupStatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="gstmt1@test.com", username="gstmt1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MGRST01",
            first_name="Group",
            last_name="Member",
            phone_number="+255712000301",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="StmtGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        GroupMembership.objects.create(group=self.group, member=self.member, is_active=True)
        self.cash = get_or_create_group_cash_account(self.group)
        self.ms = get_or_create_member_savings_account(self.account)
        self.clearing = get_org_account("1100-CLEARING")
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _book(self, amount, tx_type, key, member=True):
        if tx_type == FinancialTransaction.TransactionType.WITHDRAWAL:
            entries = [
                {"account": self.ms, "entry_type": "DEBIT", "amount": amount},
                {"account": self.cash, "entry_type": "CREDIT", "amount": amount},
            ]
        elif tx_type == FinancialTransaction.TransactionType.LOAN_DISBURSEMENT:
            entries = [
                {"account": get_org_account("1300-LOAN_PRINCIPAL"), "entry_type": "DEBIT", "amount": amount},
                {"account": self.clearing, "entry_type": "CREDIT", "amount": amount},
            ]
        else:
            entries = [
                {"account": self.cash, "entry_type": "DEBIT", "amount": amount},
                {"account": self.ms, "entry_type": "CREDIT", "amount": amount},
            ]
        tx, _ = post_transaction(
            transaction_type=tx_type,
            amount=Decimal(amount),
            entries=entries,
            group=self.group,
            member=self.member if member else None,
            reference=f"GRPSTMT-{key}",
        )
        return tx

    def test_group_statement_running_balance_follows_journal(self):
        self._book("1000.00", FinancialTransaction.TransactionType.DEPOSIT, "d1")
        self._book("2000.00", FinancialTransaction.TransactionType.DEPOSIT, "d2")
        self._book("500.00", FinancialTransaction.TransactionType.WITHDRAWAL, "w1")
        resp = self.member_client.get(f"/api/v1/groups/{self.group.pk}/statement")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "group_savings")
        self.assertEqual(body["opening_balance"], "0.00")
        self.assertEqual(body["closing_balance"], "2500.00")
        self.assertEqual(len(body["rows"]), 3)
        self.assertEqual(body["rows"][-1]["running_balance"], "2500.00")
        self.assertEqual(body["summary"]["inflows"], "3000.00")
        self.assertEqual(body["summary"]["outflows"], "500.00")

    def test_group_statement_period_bounds_shift_opening(self):
        first = self._book("1000.00", FinancialTransaction.TransactionType.DEPOSIT, "p1")
        first.posted_at = dj_timezone.make_aware(datetime(2026, 1, 2))
        first.save(update_fields=["posted_at"])
        self._book("2000.00", FinancialTransaction.TransactionType.DEPOSIT, "p2")
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/statement?start=2026-01-03"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["opening_balance"], "1000.00")
        self.assertEqual(body["closing_balance"], "3000.00")
        self.assertEqual(len(body["rows"]), 1)

    def test_group_statement_surfaces_non_savings_flows(self):
        self._book("6000.00", FinancialTransaction.TransactionType.LOAN_DISBURSEMENT, "loan1")
        resp = self.member_client.get(f"/api/v1/groups/{self.group.pk}/statement")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        row = body["rows"][0]
        self.assertEqual(row["delta"], "0.00")
        self.assertEqual(row["running_balance"], "0.00")
        self.assertEqual(
            body["summary"]["flow_totals"][FinancialTransaction.TransactionType.LOAN_DISBURSEMENT],
            "6000.00",
        )

    def test_group_statement_invalid_period_returns_400(self):
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/statement?start=not-a-date"
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_member_cannot_read_group_statement(self):
        outsider = User.objects.create_user(
            email="gstmt2@test.com", username="gstmt2", password="pass", is_active=True
        )
        outsider.role = User.MEMBER
        outsider.save()
        Member.objects.create(
            user=outsider,
            membership_number="MGRST02",
            first_name="Other",
            last_name="Member",
            phone_number="+255712000302",
        )
        client = APIClient()
        client.force_authenticate(user=outsider)
        resp = client.get(f"/api/v1/groups/{self.group.pk}/statement")
        self.assertEqual(resp.status_code, 403)