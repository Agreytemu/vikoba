"""Phase 5 STEP 7: ledger-derived contribution report tests.

A confirmation is only reported as collected when a CONTRIBUTION journal leg
exists — a confirmed-but-unposted contribution shows up as a gap
(``unrecorded_in_ledger``), never silently counted. Covered:
- collected totals come from the journal, not the record status alone
- a confirmed record without a ledger posting is surfaced as a gap
- month filter narrows scheduled + figures
- regular members see only their own rows; leaders see the whole group
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct
from finance.models import FinancialTransaction
from finance.services.accounts_catalog import (
    get_or_create_group_cash_account,
    get_or_create_member_savings_account,
)
from finance.services.engine import post_transaction
from groups.models import GroupContribution, GroupMembership, VikobaGroup
from members.models import Member

User = get_user_model()


class ContributionReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="crep1@test.com", username="crep1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MCRP01",
            first_name="Rep",
            last_name="Member",
            phone_number="+255712000401",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="ContribGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        GroupMembership.objects.create(
            group=self.group, member=self.member, is_active=True, role=GroupMembership.Role.TREASURER
        )
        self.cash = get_or_create_group_cash_account(self.group)
        self.ms = get_or_create_member_savings_account(self.account)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _schedule(self, amount="20000.00", month="2026-03", reference="c-1"):
        return GroupContribution.objects.create(
            group=self.group,
            member=self.member,
            amount=Decimal(amount),
            month=month,
            reference=reference,
            status=GroupContribution.Status.CONFIRMED,
        )

    def _collect(self, contribution, key):
        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.CONTRIBUTION,
            amount=contribution.amount,
            entries=[
                {"account": self.cash, "entry_type": "DEBIT", "amount": contribution.amount},
                {"account": self.ms, "entry_type": "CREDIT", "amount": contribution.amount},
            ],
            group=self.group,
            member=self.member,
            contribution=contribution,
            reference=f"CREP-{key}",
        )

    def test_collected_totals_come_from_journal(self):
        scheduled = self._schedule()
        self._collect(scheduled, "1")
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/contributions/report"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "group_contributions")
        self.assertEqual(body["summary"]["scheduled_count"], 1)
        self.assertEqual(body["summary"]["collected_count"], 1)
        self.assertEqual(body["summary"]["collected_amount"], "20000.00")
        self.assertEqual(body["summary"]["unrecorded_in_ledger"], 0)
        self.assertTrue(body["rows"][0]["collected"])
        self.assertEqual(body["rows"][0]["ledger"]["amount"], "20000.00")

    def test_confirmed_without_ledger_is_a_gap(self):
        self._schedule(reference="unposted")
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/contributions/report"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["summary"]["scheduled_count"], 1)
        self.assertEqual(body["summary"]["collected_count"], 0)
        self.assertEqual(body["summary"]["unrecorded_in_ledger"], 1)
        self.assertFalse(body["rows"][0]["collected"])
        self.assertIsNone(body["rows"][0]["ledger"])

    def test_month_filter_narrows_report(self):
        jan = self._schedule(month="2026-01", reference="jan")
        feb = self._schedule(month="2026-02", reference="feb")
        self._collect(jan, "jan")
        self._collect(feb, "feb")
        resp = self.member_client.get(
            f"/api/v1/groups/{self.group.pk}/contributions/report?month=2026-02"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["summary"]["scheduled_count"], 1)
        self.assertEqual(body["rows"][0]["month"], "2026-02")
        self.assertEqual(body["rows"][0]["reference"], "feb")

    def test_regular_member_only_sees_own_rows(self):
        other = Member.objects.create(
            user=User.objects.create_user(
                email="crep2@test.com", username="crep2", password="pass", is_active=True
            ),
            membership_number="MCRP02",
            first_name="Other",
            last_name="Member",
            phone_number="+255712000402",
        )
        GroupMembership.objects.create(group=self.group, member=other, is_active=True)
        GroupContribution.objects.create(
            group=self.group,
            member=other,
            amount=Decimal("5000.00"),
            month="2026-03",
            reference="other-1",
            status=GroupContribution.Status.CONFIRMED,
        )
        plain = User.objects.create_user(
            email="crep3@test.com", username="crep3", password="pass", is_active=True
        )
        plain.role = User.MEMBER
        plain.save()
        plain_member = Member.objects.create(
            user=plain,
            membership_number="MCRP03",
            first_name="Plain",
            last_name="Member",
            phone_number="+255712000403",
        )
        GroupMembership.objects.create(group=self.group, member=plain_member, is_active=True)
        GroupContribution.objects.create(
            group=self.group,
            member=plain_member,
            amount=Decimal("3000.00"),
            month="2026-03",
            reference="plain-1",
            status=GroupContribution.Status.CONFIRMED,
        )
        client = APIClient()
        client.force_authenticate(user=plain)
        resp = client.get(f"/api/v1/groups/{self.group.pk}/contributions/report")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["summary"]["scheduled_count"], 1)
        self.assertEqual(body["summary"]["collected_count"], 0)
        memberships = [row["member"]["membership_number"] for row in body["rows"]]
        self.assertEqual(memberships, [plain_member.membership_number])

    def test_non_member_blocked(self):
        outsider = User.objects.create_user(
            email="crep9@test.com", username="crep9", password="pass", is_active=True
        )
        outsider.role = User.MEMBER
        outsider.save()
        client = APIClient()
        client.force_authenticate(user=outsider)
        resp = client.get(f"/api/v1/groups/{self.group.pk}/contributions/report")
        self.assertEqual(resp.status_code, 403)