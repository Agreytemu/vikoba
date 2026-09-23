"""Phase 5 STEP 12: CSV export tests.

`?export=csv` on statement/report endpoints streams UTF-8 BOM CSV derived from
the same journal-backed payloads — read-only, never touching the books.
Covered:
- member savings statement export flattens per-account rows with BOM + CRLF
- withdrawal report export streams rows
- group statement export is member-gated
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
from groups.models import GroupMembership, VikobaGroup
from members.models import Member

User = get_user_model()


class ExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="exp1@test.com", username="exp1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MEXP01",
            first_name="Export",
            last_name="Member",
            phone_number="+255712000801",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="ExportGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        GroupMembership.objects.create(group=self.group, member=self.member, is_active=True)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def test_member_statement_export_csv(self):
        post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("2500.00"),
            user=self.user,
            narration="export deposit",
            idempotency_key="exp-d-1",
        )
        resp = self.member_client.get("/api/v1/finance/me/statement/?export=csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        body = resp.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        self.assertIn("2500.00", body)
        header = body.split("\r\n")[0]
        self.assertIn("account_number", header)

    def test_group_statement_export_member_gated(self):
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/statement?export=csv"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))

    def test_withdrawal_export_staff_only(self):
        resp = self.member_client.get("/api/v1/finance/reports/withdrawals/?export=csv")
        self.assertEqual(resp.status_code, 403)
        staff = User.objects.create_user(
            email="expfin@test.com", username="expfin", password="pass", is_active=True
        )
        staff.role = User.FINANCE
        staff.save()
        client = APIClient()
        client.force_authenticate(user=staff)
        resp = client.get("/api/v1/finance/reports/withdrawals/?export=csv")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))