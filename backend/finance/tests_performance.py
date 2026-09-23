"""Phase 5 STEP 13: report query-shape guard tests.

The statement/report builders must not degrade into N+1 queries as members
add accounts or groups add transactions. The bounds are deliberately generous
(authorization/session setup adds its own queries); they exist to catch a
regression that turns a statement into a query-per-row loop.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction
from accounts.services import post_savings_transaction
from finance.services.statements import (
    run_group_savings_statement,
    run_member_savings_statement,
)
from groups.models import GroupMembership, VikobaGroup
from members.models import Member

User = get_user_model()


class ReportQueryShapeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="perf1@test.com", username="perf1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MPERF01",
            first_name="Perf",
            last_name="Member",
            phone_number="+255712000901",
            is_verified=True,
        )
        self.accounts = []
        for i in range(3):
            product = SavingsProduct.objects.create(
                name=f"Perf {i}", code=f"PRF{i}", is_active=True,
            )
            account = SavingsAccount.objects.create(
                member=self.member, product=product, balance=Decimal("0.00")
            )
            self.accounts.append(account)
            for j in range(3):
                post_savings_transaction(
                    account=account,
                    transaction_type=SavingsTransaction.DEPOSIT,
                    amount=Decimal("1000.00"),
                    user=self.user,
                    narration=f"perf {i}-{j}",
                    idempotency_key=f"perf-{i}-{j}",
                )
        self.group = VikobaGroup.objects.create(
            name="PerfGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        GroupMembership.objects.create(group=self.group, member=self.member, is_active=True)

    def test_member_statement_query_count_stable(self):
        with CaptureQueriesContext(connection) as ctx:
            report = run_member_savings_statement(self.member)
        self.assertEqual(len(report["accounts"]), 3)
        self.assertLess(len(ctx), 60)

    def test_group_statement_query_count_stable(self):
        from finance.models import FinancialTransaction
        from finance.services.accounts_catalog import (
            get_or_create_group_cash_account,
            get_or_create_member_savings_account,
        )
        from finance.services.engine import post_transaction

        cash = get_or_create_group_cash_account(self.group)
        ms = get_or_create_member_savings_account(self.accounts[0])
        for i in range(9):
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.CONTRIBUTION,
                amount=Decimal("2000.00"),
                entries=[
                    {"account": cash, "entry_type": "DEBIT", "amount": "2000.00"},
                    {"account": ms, "entry_type": "CREDIT", "amount": "2000.00"},
                ],
                group=self.group,
                member=self.member,
                reference=f"PERF-G-{i}",
            )
        with CaptureQueriesContext(connection) as ctx:
            report = run_group_savings_statement(self.group)
        self.assertGreaterEqual(len(report["rows"]), 9)
        self.assertLess(len(ctx), 40)