"""Phase 5 STEP 9: journal-reconstructed loan statement tests.

The statement derives outstanding principal from the 1300-LOAN_PRINCIPAL legs,
disbursement and repayment split off their income-account legs. Covered:
- outstanding principal is reconstructed from the journal for disbursement +
  full/partial repayments
- period bounds shift the opening outstanding
- member endpooint scoped to the borrower (other members cannot reach it)
- staff endpoint readable by finance role only
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone as dj_timezone
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct
from finance.models import FinancialTransaction
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction
from loans.models import LoanAccount, LoanProduct
from members.models import Member

User = get_user_model()


class LoanStatementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="lone1@test.com", username="lone1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MLONE01",
            first_name="Loan",
            last_name="Member",
            phone_number="+255712000601",
            is_verified=True,
        )
        self.product = LoanProduct.objects.create(
            name="Stmt Loan",
            interest_rate=Decimal("12.00"),
            repayment_period_months=12,
            multiplier=Decimal("3.00"),
            min_amount=Decimal("1000.00"),
            max_amount=Decimal("500000.00"),
            max_term_months=24,
            requires_guarantors=False,
            interest_type=LoanProduct.FLAT,
            is_active=True,
        )
        self.loan = LoanAccount.objects.create(
            loan_number="LSTMT01",
            member=self.member,
            product=self.product,
            principal_amount=Decimal("100000.00"),
            interest_rate=Decimal("12.00"),
            term_months=12,
            status=LoanAccount.DISBURSED,
            outstanding_principal=Decimal("100000.00"),
            outstanding_interest=Decimal("0.00"),
            created_by=self.user,
        )
        self.clearing = get_org_account("1100-CLEARING")
        self.principal = get_org_account("1300-LOAN_PRINCIPAL")
        self.interest = get_org_account("4001-INTEREST_INCOME")
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)
        self.staff = User.objects.create_user(
            email="lonefin@test.com", username="lonefin", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)

    def _disburse(self, amount="100000.00"):
        return post_transaction(
            transaction_type=FinancialTransaction.TransactionType.LOAN_DISBURSEMENT,
            amount=Decimal(amount),
            entries=[
                {"account": self.principal, "entry_type": "DEBIT", "amount": amount},
                {"account": self.clearing, "entry_type": "CREDIT", "amount": amount},
            ],
            member=self.member,
            loan=self.loan,
            reference=f"LSTMT-D-{self.loan.loan_number}",
        )[0]

    def _repay(self, principal, interest, key):
        applied = Decimal(principal) + Decimal(interest)
        entries = [
            {"account": self.clearing, "entry_type": "DEBIT", "amount": str(applied)},
            {"account": self.principal, "entry_type": "CREDIT", "amount": principal},
            {"account": self.interest, "entry_type": "CREDIT", "amount": interest},
        ]
        return post_transaction(
            transaction_type=FinancialTransaction.TransactionType.LOAN_REPAYMENT,
            amount=applied,
            entries=entries,
            member=self.member,
            loan=self.loan,
            reference=f"LSTMT-R-{key}",
        )[0]

    def test_outstanding_reconstructed_from_journal(self):
        self._disburse()
        self._repay("40000.00", "8000.00", "1")
        self._repay("30000.00", "6000.00", "2")
        resp = self.staff_client.get(
            f"/api/v1/finance/loans/{self.loan.loan_number}/statement/"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["statement"], "loan")
        self.assertEqual(body["opening_outstanding"], "0.00")
        self.assertEqual(body["closing_outstanding"], "30000.00")
        self.assertEqual(body["summary"]["disbursed"], "100000.00")
        self.assertEqual(body["summary"]["repaid_principal"], "70000.00")
        self.assertEqual(body["summary"]["repaid_interest"], "14000.00")
        self.assertEqual(len(body["rows"]), 3)
        self.assertEqual(body["rows"][-1]["running_outstanding"], "30000.00")

    def test_period_bounds_shift_opening_outstanding(self):
        first = self._disburse()
        first.posted_at = dj_timezone.make_aware(datetime(2026, 1, 2))
        first.save(update_fields=["posted_at"])
        repayment = self._repay("40000.00", "8000.00", "3")
        repayment.posted_at = dj_timezone.make_aware(datetime(2026, 2, 2))
        repayment.save(update_fields=["posted_at"])
        resp = self.staff_client.get(
            f"/api/v1/finance/loans/{self.loan.loan_number}/statement/?start=2026-02-01"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["opening_outstanding"], "100000.00")
        self.assertEqual(body["closing_outstanding"], "60000.00")
        self.assertEqual(len(body["rows"]), 1)

    def test_member_can_read_own_loan_statement(self):
        self._disburse()
        resp = self.member_client.get(
            f"/api/v1/loans/me/accounts/{self.loan.loan_number}/statement/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["closing_outstanding"], "100000.00")

    def test_member_cannot_read_other_loan_statement(self):
        other_user = User.objects.create_user(
            email="lone2@test.com", username="lone2", password="pass", is_active=True
        )
        other_user.role = User.MEMBER
        other_user.save()
        other_member = Member.objects.create(
            user=other_user,
            membership_number="MLONE02",
            first_name="Other",
            last_name="Loan",
            phone_number="+255712000602",
        )
        client = APIClient()
        client.force_authenticate(user=other_user)
        resp = client.get(f"/api/v1/loans/me/accounts/{self.loan.loan_number}/statement/")
        self.assertIn(resp.status_code, (403, 404))

    def test_member_cannot_use_staff_loan_report(self):
        resp = self.member_client.get(
            f"/api/v1/finance/loans/{self.loan.loan_number}/statement/"
        )
        self.assertEqual(resp.status_code, 403)