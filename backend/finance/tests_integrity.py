"""Phase 5 STEP 2: financial integrity monitor tests.

The monitor is a read-only sanity layer over the double-entry journal. These
tests prove it flags the exact failure classes the audit identified:
- an unbalanced journal that sneaks past the engine
- a financial transaction with no journal legs
- a settled (SUCCESS) payment that never produced a posting
- cached SavingsAccount.balance diverging from the ledger
- stored loan outstanding_principal diverging from the journal
- duplicate provider references (and the DB guard that prevents them)
plus API authorization for the staff-only integrity endpoint.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from django.test import TestCase

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction
from accounts.services import post_savings_transaction
from finance.models import FinancialTransaction, JournalEntry
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction
from finance.services.integrity import run_integrity_checks
from groups.models import VikobaGroup
from loans.models import LoanAccount, LoanProduct
from members.models import Member
from payments.models import PaymentTransaction

User = get_user_model()


class IntegrityBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member-int@test.com", username="member-int", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTESTINT01",
            first_name="Test",
            last_name="Member",
            phone_number="+255711111111",
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
            email="fin-int@test.com", username="fin-int", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _deposit(self, amount="10000.00"):
        sav_tx = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal(amount),
            user=self.user,
            narration="integrity deposit",
            idempotency_key=f"int-dep-{amount}",
        )
        return sav_tx.financial_transactions.first()


class IntegrityCheckTests(IntegrityBase):
    def test_clean_books_pass_all_checks(self):
        self._deposit()
        report = run_integrity_checks()
        self.assertTrue(report["ok"])
        self.assertEqual(report["checks"]["unbalanced_journals"]["count"], 0)
        self.assertEqual(report["checks"]["transactions_without_entries"]["count"], 0)
        self.assertEqual(report["checks"]["completed_payments_unposted"]["count"], 0)
        self.assertEqual(report["checks"]["savings_drift"]["count"], 0)
        self.assertEqual(report["checks"]["loan_drift"]["count"], 0)
        self.assertEqual(report["checks"]["duplicate_provider_references"]["count"], 0)

    def test_unbalanced_journal_detected(self):
        fin_tx = self._deposit(amount="1000.00")
        JournalEntry.objects.create(
            transaction=fin_tx,
            account=get_org_account("1100-CLEARING"),
            entry_type=JournalEntry.DEBIT,
            amount="1.00",
            position=9,
        )
        report = run_integrity_checks()
        self.assertFalse(report["ok"])
        self.assertIn("unbalanced_journals", report["error_checks"])
        sample = report["checks"]["unbalanced_journals"]["samples"][0]
        self.assertEqual(sample["reference"], fin_tx.reference)

    def test_transaction_without_entries_detected(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.ADJUSTMENT,
            amount="500.00",
            status=FinancialTransaction.Status.SUCCESS,
            reference="INTEG-NOLEGS",
        )
        report = run_integrity_checks()
        self.assertFalse(report["ok"])
        self.assertIn("transactions_without_entries", report["error_checks"])
        self.assertEqual(report["checks"]["transactions_without_entries"]["count"], 1)

    def test_completed_payment_without_posting_detected(self):
        PaymentTransaction.objects.create(
            member=self.member,
            group=self.group,
            transaction_type=PaymentTransaction.Type.CONTRIBUTION,
            amount=Decimal("2000.00"),
            status=PaymentTransaction.Status.SUCCESS,
            idempotency_key="int-key-unposted-1",
        )
        report = run_integrity_checks()
        self.assertFalse(report["ok"])
        self.assertIn("completed_payments_unposted", report["error_checks"])
        self.assertEqual(report["checks"]["completed_payments_unposted"]["count"], 1)

    def test_savings_balance_drift_detected(self):
        self._deposit(amount="5000.00")
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("5000.00"))
        self.account.balance = Decimal("5000.01")
        self.account.save(update_fields=["balance"])
        report = run_integrity_checks()
        self.assertFalse(report["ok"])
        self.assertIn("savings_drift", report["error_checks"])
        sample = report["checks"]["savings_drift"]["samples"][0]
        self.assertEqual(sample["cached"], "5000.01")
        self.assertEqual(sample["ledger"], "5000.00")

    def test_loan_principal_drift_detected(self):
        loan = LoanAccount.objects.create(
            member=self.member,
            product=LoanProduct.objects.create(
                name="Integrity Loan",
                interest_rate=Decimal("10.00"),
                repayment_period_months=12,
                multiplier=Decimal("3.00"),
                min_amount=Decimal("1000.00"),
                max_amount=Decimal("500000.00"),
                max_term_months=24,
                interest_type=LoanProduct.REDUCING,
                is_active=True,
            ),
            principal_amount=Decimal("500000.00"),
            interest_rate=Decimal("10.00"),
            term_months=12,
            status=LoanAccount.DISBURSED,
            outstanding_principal=Decimal("0.00"),
            created_by=self.staff,
        )
        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.LOAN_DISBURSEMENT,
            amount="500000.00",
            member=self.member,
            loan=loan,
            entries=[
                {"account": get_org_account("1300-LOAN_PRINCIPAL"), "entry_type": "DEBIT", "amount": "500000.00"},
                {"account": get_org_account("1100-CLEARING"), "entry_type": "CREDIT", "amount": "500000.00"},
            ],
        )
        report = run_integrity_checks()
        self.assertFalse(report["ok"])
        self.assertIn("loan_drift", report["error_checks"])
        sample = report["checks"]["loan_drift"]["samples"][0]
        self.assertEqual(sample["loan_number"], loan.loan_number)
        self.assertEqual(sample["expected_outstanding"], "500000.00")
        self.assertEqual(sample["stored_outstanding"], "0.00")

    def test_duplicate_provider_reference_is_database_guarded(self):
        PaymentTransaction.objects.create(
            member=self.member,
            transaction_type=PaymentTransaction.Type.OTHER,
            amount=Decimal("100.00"),
            status=PaymentTransaction.Status.PENDING,
            provider_reference="SHARED-REF",
            idempotency_key="int-key-dupe-1",
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                PaymentTransaction.objects.create(
                    member=self.member,
                    transaction_type=PaymentTransaction.Type.OTHER,
                    amount=Decimal("100.00"),
                    status=PaymentTransaction.Status.PENDING,
                    provider_reference="SHARED-REF",
                    idempotency_key="int-key-dupe-2",
                )
        report = run_integrity_checks()
        self.assertEqual(report["checks"]["duplicate_provider_references"]["count"], 0)


class IntegrityAPITests(IntegrityBase):
    def test_staff_can_run_integrity_report(self):
        resp = self.staff_client.get("/api/v1/finance/integrity/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("checks", body)
        self.assertIn("ok", body)
        self.assertIn("unbalanced_journals", body["checks"])

    def test_member_cannot_run_integrity_report(self):
        resp = self.member_client.get("/api/v1/finance/integrity/")
        self.assertEqual(resp.status_code, 403)

    def test_integrity_endpoint_detects_issue(self):
        PaymentTransaction.objects.create(
            member=self.member,
            group=self.group,
            transaction_type=PaymentTransaction.Type.SUBSCRIPTION,
            amount=Decimal("1500.00"),
            status=PaymentTransaction.Status.SUCCESS,
            idempotency_key="int-key-api-1",
        )
        resp = self.staff_client.get("/api/v1/finance/integrity/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["checks"]["completed_payments_unposted"]["count"], 1)