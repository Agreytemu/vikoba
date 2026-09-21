import hashlib
import hmac
import json
import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction, WithdrawalRequest
from accounts.services import post_savings_transaction
from groups.models import GroupContribution, VikobaGroup
from loans.models import LoanAccount, LoanApplication, LoanProduct, LoanSchedule, LoanTransaction
from members.models import Member

from .models import PaymentTransaction, ReconciliationRecord, WebhookEvent
from .services.payment_service import (
    handle_payment_completed,
    handle_payment_failed,
    handle_payout_completed,
    handle_payout_failed,
    initiate_contribution_payment,
    initiate_loan_repayment,
    initiate_savings_deposit,
)
from .services.payout_service import auto_withdraw, initiate_withdrawal_payout
from .webhooks.snippe import WebhookDispatcher, WebhookVerificationError, WebhookVerifier

User = get_user_model()
WEBHOOK_SECRET = getattr(settings, "SNIPPE_WEBHOOK_SECRET", "") or "test-webhook-secret"


def _webhook_event_id():
    return f"evt_{int(time.time()*1000)}_{id(WEBHOOK_SECRET):x}"


def _signed(body_dict, secret=WEBHOOK_SECRET, ts=None):
    raw = json.dumps(body_dict, separators=(",", ":"))
    t = ts or str(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{raw}".encode(), hashlib.sha256).hexdigest()
    return raw, t, sig


class ContributionPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="member1@test.com", username="member1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST001",
            first_name="Test",
            last_name="Member",
            phone_number="+255712345678",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        self.group = VikobaGroup.objects.create(name="TestGroup", area="Dar", country="Tanzania", created_by=self.member)
        self.group.memberships.create(member=self.member, role="member", shares_count=1)

    def test_initiate_creates_pending_contribution_and_tx(self):
        tx = initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal("10000"),
            month="2026-01",
            phone="+255712345678",
        )
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertIsNotNone(tx.provider_reference)
        self.assertTrue(tx.provider_reference.startswith("snp_dev_pay_"))
        contribution = tx.contribution
        self.assertEqual(contribution.status, GroupContribution.Status.PENDING)
        self.assertEqual(contribution.amount, Decimal("10000"))

    def test_webhook_completed_confirms_contribution_and_credits_savings(self):
        tx = initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal("50000"),
            month="2026-02",
        )
        provider_reference = tx.provider_reference
        event = WebhookEvent.objects.create(
            event_id=_webhook_event_id(),
            event_type="payment.completed",
            payload={
                "reference": provider_reference,
                "amount": {"value": 50000, "currency": "TZS"},
                "settlement": {"gross": 50000, "fees": 0, "net": 50000},
                "channel": {"type": "mobile", "provider": "Tigo"},
            },
        )
        handle_payment_completed(event, event.payload)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(tx.amount, Decimal("50000"))
        self.assertEqual(tx.fee, Decimal("0"))
        self.assertIsNotNone(tx.completed_at)
        tx.contribution.refresh_from_db()
        self.assertEqual(tx.contribution.status, GroupContribution.Status.CONFIRMED)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("50000"))

    def test_webhook_completed_idempotent_no_double_credit(self):
        tx = initiate_contribution_payment(member=self.member, group=self.group, amount=Decimal("75000"), month="2026-03")
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 75000, "currency": "TZS"},
            "settlement": {"gross": 75000, "fees": 0, "net": 75000},
            "channel": {"type": "mobile"},
        }
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload=payload)
        handle_payment_completed(event, payload)
        self.account.refresh_from_db()
        balance_after_first = self.account.balance
        # Simulate a second delivery of the exact same event
        handle_payment_completed(event, payload)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, balance_after_first)

    def test_webhook_failed_rejects_contribution_no_savings_credit(self):
        tx = initiate_contribution_payment(member=self.member, group=self.group, amount=Decimal("30000"), month="2026-04")
        event = WebhookEvent.objects.create(
            event_id=_webhook_event_id(),
            event_type="payment.failed",
            payload={"reference": tx.provider_reference, "message": "User declined", "amount": {"value": 30000}},
        )
        handle_payment_failed(event, event.payload)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(tx.failure_reason, "User declined")
        tx.contribution.refresh_from_db()
        self.assertEqual(tx.contribution.status, GroupContribution.Status.REJECTED)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("0.00"))


class LoanRepaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="loanmember1@test.com", username="loanmember1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST002",
            first_name="Loan",
            last_name="Borrower",
            phone_number="+255798765432",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default2", code="DEF2", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        loan_product = LoanProduct.objects.create(name="PersonalLoan", interest_rate=Decimal("12"), interest_type=LoanProduct.FLAT, is_active=True, min_amount=Decimal("5000"), max_amount=Decimal("5000000"), max_term_months=36)
        # Manually create a disbursed loan with schedule
        self.loan = LoanAccount.objects.create(
            member=self.member,
            product=loan_product,
            principal_amount=Decimal("100000"),
            interest_rate=Decimal("12"),
            term_months=3,
            status=LoanAccount.DISBURSED,
            disbursed_at=timezone.now(),
            outstanding_principal=Decimal("100000"),
            outstanding_interest=Decimal("3000"),
            created_by=self.user,
        )
        self.schedule1 = LoanSchedule.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=timezone.now().date(),
            principal_due=Decimal("33333.34"),
            interest_due=Decimal("1000.00"),
            total_due=Decimal("34333.34"),
            is_paid=False,
        )
        self.schedule2 = LoanSchedule.objects.create(
            loan=self.loan,
            installment_number=2,
            due_date=timezone.now().date(),
            principal_due=Decimal("33333.33"),
            interest_due=Decimal("1000.00"),
            total_due=Decimal("34333.33"),
            is_paid=False,
        )

    def test_initiate_creates_pending_loan_repayment_tx(self):
        tx = initiate_loan_repayment(member=self.member, loan=self.loan, installment_number=1)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(tx.transaction_type, PaymentTransaction.Type.LOAN_REPAYMENT)
        self.assertEqual(tx.amount, Decimal("34333.34"))
        self.assertIsNotNone(tx.provider_reference)

    def test_webhook_completed_settles_installment_updates_loan(self):
        tx = initiate_loan_repayment(member=self.member, loan=self.loan, installment_number=1)
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 34333, "currency": "TZS"},
            "settlement": {"gross": 34333, "fees": 0, "net": 34333},
            "channel": {"type": "mobile"},
        }
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload=payload)
        handle_payment_completed(event, payload)
        self.schedule1.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertTrue(self.schedule1.is_paid)
        self.assertIsNotNone(self.schedule1.paid_at)
        self.assertIsNotNone(self.schedule1.payment_transaction)
        self.assertTrue(self.schedule1.payment_transaction.reference.startswith("PAY-"))
        self.assertEqual(self.loan.outstanding_principal, Decimal("66666.66"))
        self.schedule2.refresh_from_db()
        # Only installment 1 was repaid; the rest of the schedule stays due.
        self.assertFalse(self.schedule2.is_paid)

    def test_webhook_completed_idempotent_no_double_settle(self):
        tx = initiate_loan_repayment(member=self.member, loan=self.loan, installment_number=2)
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 34333, "currency": "TZS"},
            "settlement": {"gross": 34333, "fees": 0, "net": 34333},
            "channel": {"type": "mobile"},
        }
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload=payload)
        handle_payment_completed(event, payload)
        tx.refresh_from_db()
        self.loan.refresh_from_db()
        first_principal = self.loan.outstanding_principal
        self.account.refresh_from_db()
        handle_payment_completed(event, payload)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.outstanding_principal, first_principal)


class WithdrawalPayoutTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email="staff1@test.com", username="staff1", password="pass", is_active=True)
        self.staff.role = User.ADMIN
        self.staff.save()
        self.member = Member.objects.create(
            membership_number="MTEST003",
            first_name="Cash",
            last_name="Out",
            phone_number="+255711223344",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default3", code="DEF3", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("200000"))
        self.withdrawal = WithdrawalRequest.objects.create(
            member=self.member,
            account=self.account,
            amount=Decimal("50000"),
            status=WithdrawalRequest.Status.APPROVED,
            processed_by=self.staff,
        )

    def test_initiate_withdrawal_payout_creates_sent_to_snippe_status(self):
        tx = initiate_withdrawal_payout(withdrawal=self.withdrawal)
        self.assertEqual(tx.status, PaymentTransaction.Status.PROCESSING)
        self.assertEqual(tx.transaction_type, PaymentTransaction.Type.WITHDRAWAL)
        self.assertIsNotNone(tx.provider_reference)
        self.assertTrue(tx.provider_reference.startswith("snp_dev_payout_"))
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, WithdrawalRequest.Status.SENT_TO_SNIPPE)

    def test_payout_completed_debits_savings_and_sets_success(self):
        initiate_withdrawal_payout(withdrawal=self.withdrawal)
        self.withdrawal.refresh_from_db()
        tx = PaymentTransaction.objects.filter(withdrawal=self.withdrawal).first()
        payload = {
            "reference": tx.provider_reference,
            "amount": 50000,
            "currency": "TZS",
            "recipient_phone": "+255711223344",
        }
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payout.completed", payload=payload)
        handle_payout_completed(event, payload)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("150000"))
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, WithdrawalRequest.Status.SUCCESS)

    def test_payout_failed_sets_failed_no_debit(self):
        initiate_withdrawal_payout(withdrawal=self.withdrawal)
        self.withdrawal.refresh_from_db()
        tx = PaymentTransaction.objects.filter(withdrawal=self.withdrawal).first()
        payload = {"reference": tx.provider_reference, "message": "Insufficient funds", "amount": 50000}
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payout.failed", payload=payload)
        handle_payout_failed(event, payload)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("200000"))
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, WithdrawalRequest.Status.FAILED)

    def test_payout_fails_after_dispatch_undoes_reservation(self):
        """On provider rejection (e.g. bad phone), no money moves; the withdrawal
        stays APPROVED and the failed attempt is recorded for audit."""
        from unittest.mock import patch
        from .services.snippe import SnippeError

        with self.assertRaises(Exception):
            with patch("payments.services.payout_service.SnippeProvider") as MockProvider:
                MockProvider.return_value.create_payout.side_effect = SnippeError("bad phone", code="invalid_phone")
                initiate_withdrawal_payout(withdrawal=self.withdrawal)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("200000"))
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, WithdrawalRequest.Status.APPROVED)
        failed = PaymentTransaction.objects.filter(withdrawal=self.withdrawal).first()
        self.assertIsNotNone(failed)
        self.assertEqual(failed.status, PaymentTransaction.Status.FAILED)


class SavingsDepositTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="dep1@test.com", username="dep1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST010",
            first_name="Dep",
            last_name="Sit",
            phone_number="+255700112233",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Basic", code="BASIC", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))

    def test_initiate_creates_pending_deposit_tx(self):
        tx = initiate_savings_deposit(member=self.member, amount=Decimal("20000"), phone="+255700112233")
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(tx.transaction_type, PaymentTransaction.Type.DEPOSIT)
        self.assertIsNotNone(tx.provider_reference)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("0.00"))

    def test_webhook_completed_credits_savings(self):
        tx = initiate_savings_deposit(member=self.member, amount=Decimal("20000"), phone="+255700112233")
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 20000, "currency": "TZS"},
            "settlement": {"gross": 20000, "fees": 0, "net": 20000},
            "channel": {"type": "mobile", "provider": "M-Pesa"},
        }
        event = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload=payload)
        handle_payment_completed(event, payload)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("20000"))

    def test_initiate_requires_savings_account(self):
        other = Member.objects.create(
            membership_number="MTEST011",
            first_name="No",
            last_name="Account",
            phone_number="+255700112244",
            is_verified=True,
        )
        with self.assertRaises(ValueError):
            initiate_savings_deposit(member=other, amount=Decimal("20000"))


class AutoWithdrawalTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            membership_number="MTEST012",
            first_name="Auto",
            last_name="Draw",
            phone_number="+255700112255",
            is_verified=True,
            phone_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="AutoBasic", code="AUTOBASIC", is_active=True, allows_withdrawals=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("200000"))

    def test_auto_withdraw_approves_and_sends(self):
        withdrawal, tx = auto_withdraw(
            member=self.member,
            account=self.account,
            amount=Decimal("50000"),
            narration="Wallet withdrawal",
        )
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.SENT_TO_SNIPPE)
        self.assertEqual(tx.transaction_type, PaymentTransaction.Type.WITHDRAWAL)
        self.assertEqual(tx.metadata["network"], "mpesa")
        self.account.refresh_from_db()
        # Ledger debit only happens on the payout.completed webhook.
        self.assertEqual(self.account.balance, Decimal("200000"))

    def test_auto_withdraw_uses_chosen_network(self):
        withdrawal, tx = auto_withdraw(
            member=self.member,
            account=self.account,
            amount=Decimal("50000"),
            network="airtel",
        )
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.SENT_TO_SNIPPE)
        self.assertEqual(tx.metadata["network"], "airtel")

    def test_auto_withdraw_rejects_unknown_network(self):
        with self.assertRaises(ValueError):
            auto_withdraw(
                member=self.member,
                account=self.account,
                amount=Decimal("50000"),
                network="telkom",
            )

    def test_auto_withdraw_rejects_unverified(self):
        self.member.is_verified = False
        self.member.save()
        with self.assertRaises(ValueError):
            auto_withdraw(member=self.member, account=self.account, amount=Decimal("50000"))

    def test_auto_withdraw_rejects_unverified_phone(self):
        self.member.phone_verified = False
        self.member.save()
        with self.assertRaises(ValueError):
            auto_withdraw(member=self.member, account=self.account, amount=Decimal("50000"))

    def test_auto_withdraw_rejects_insufficient(self):
        with self.assertRaises(ValueError):
            auto_withdraw(member=self.member, account=self.account, amount=Decimal("9999999"))

    def test_auto_withdraw_rejects_below_minimum(self):
        with self.assertRaises(ValueError):
            auto_withdraw(member=self.member, account=self.account, amount=Decimal("500"))

    def test_auto_withdraw_only_uses_verified_number(self):
        withdrawal, tx = auto_withdraw(
            member=self.member,
            account=self.account,
            amount=Decimal("50000"),
            narration="Wallet withdrawal",
        )
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.SENT_TO_SNIPPE)
        self.assertEqual(tx.phone, "+255700112255")


class WebhookVerifierTests(TestCase):
    def test_rejects_missing_signature(self):
        verifier = WebhookVerifier(signing_key="secret")
        with self.assertRaises(WebhookVerificationError):
            verifier.verify("", "123", "body")

    def test_rejects_missing_timestamp(self):
        verifier = WebhookVerifier(signing_key="secret")
        with self.assertRaises(WebhookVerificationError):
            verifier.verify("sig", "", "body")

    def test_rejects_stale_timestamp(self):
        old_ts = str(time.time() - 400)
        verifier = WebhookVerifier(signing_key="secret")
        with self.assertRaises(WebhookVerificationError):
            verifier.verify("sig", old_ts, "body")

    def test_rejects_bad_signature(self):
        ts = str(time.time())
        verifier = WebhookVerifier(signing_key="mysecret")
        with self.assertRaises(WebhookVerificationError):
            verifier.verify("wrong-sig", ts, "body")

    def test_accepts_valid_signature(self):
        ts = str(time.time())
        body = '{"id":"evt1","type":"payment.completed","data":{}}'
        secret = "mysecret"
        sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        verifier = WebhookVerifier(signing_key=secret)
        verifier.verify(sig, ts, body)

    def test_rejects_empty_secret(self):
        verifier = WebhookVerifier(signing_key="")
        with self.assertRaises(WebhookVerificationError):
            verifier.verify("sig", str(time.time()), "body")


class WebhookEventIdempotencyTests(TestCase):
    def test_duplicate_event_id_not_double_processed(self):
        event = WebhookEvent.objects.create(event_id="duplicate_test", event_type="payment.completed", payload={"reference": "nonexistent"})
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            WebhookEvent.objects.create(event_id="duplicate_test", event_type="payment.completed", payload={})


class DevModeTests(TestCase):
    def test_dev_mode_create_payment(self):
        from .services.snippe import SnippeProvider
        provider = SnippeProvider()
        result = provider.create_payment(
            amount=Decimal("10000"),
            phone="+255712345678",
            customer={"firstname": "Test", "lastname": "User"},
            metadata={"purpose": "test"},
        )
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["reference"].startswith("snp_dev_pay_"))

    def test_dev_mode_create_payout(self):
        from .services.snippe import SnippeProvider
        provider = SnippeProvider()
        result = provider.create_payout(
            amount=Decimal("10000"),
            recipient_phone="+255712345678",
            recipient_name="Test User",
            narration="test payout",
        )
        self.assertIn(result["status"], ["pending", "processing"])
        self.assertTrue(result["reference"].startswith("snp_dev_payout_"))


class ContributionPaymentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="viewmember1@test.com", username="viewmember1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST004",
            first_name="View",
            last_name="Member",
            phone_number="+255700001122",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default4", code="DEF4", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        self.group = VikobaGroup.objects.create(name="TestGroup2", area="Dar", country="Tanzania", created_by=self.member)
        self.group.memberships.create(member=self.member, role="member", shares_count=1)
        self.login()

    def login(self):
        resp = self.client.post(
            "/api/v1/auth/login",
            {"email": "viewmember1@test.com", "password": "pass"},
            content_type="application/json",
        )
        if resp.status_code == 200:
            token = resp.json().get("access", "")
            self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        else:
            from rest_framework_simplejwt.tokens import RefreshToken
            token = str(RefreshToken.for_user(self.user).access_token)
            self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def test_contribution_pay_creates_pending(self):
        resp = self.client.post(
            "/api/v1/payments/contributions/pay/",
            {
                "group_id": str(self.group.pk),
                "amount": "10000",
                "month": "2026-01",
                "phone": "+255712345678",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "PENDING")
        self.assertIsNotNone(data["reference"])
        self.assertEqual(GroupContribution.objects.count(), 1)

    def test_contribution_pay_rejects_below_minimum(self):
        resp = self.client.post(
            "/api/v1/payments/contributions/pay/",
            {
                "group_id": str(self.group.pk),
                "amount": "100",
                "month": "2026-01",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_contribution_pay_rejects_non_member(self):
        other_group = VikobaGroup.objects.create(name="OtherGroup", area="Mwanza", country="Tanzania", created_by=self.member)
        resp = self.client.post(
            "/api/v1/payments/contributions/pay/",
            {"group_id": str(other_group.pk), "amount": "10000", "month": "2026-01"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)


class LoanRepaymentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="loanviewmember1@test.com", username="loanviewmember1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST005",
            first_name="LoanView",
            last_name="Member",
            phone_number="+255700003344",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default5", code="DEF5", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        loan_product = LoanProduct.objects.create(name="PersonalLoan2", interest_rate=Decimal("12"), interest_type=LoanProduct.FLAT, is_active=True, min_amount=Decimal("5000"), max_amount=Decimal("5000000"), max_term_months=36)
        self.loan = LoanAccount.objects.create(
            member=self.member,
            product=loan_product,
            principal_amount=Decimal("100000"),
            interest_rate=Decimal("12"),
            term_months=3,
            status=LoanAccount.DISBURSED,
            disbursed_at=timezone.now(),
            outstanding_principal=Decimal("100000"),
            outstanding_interest=Decimal("3000"),
            created_by=self.user,
        )
        self.schedule1 = LoanSchedule.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=timezone.now().date(),
            principal_due=Decimal("33333.34"),
            interest_due=Decimal("1000.00"),
            total_due=Decimal("34333.34"),
            is_paid=False,
        )
        self.login()

    def login(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def test_loan_repay_creates_pending(self):
        resp = self.client.post(
            "/api/v1/payments/loans/repay/",
            {"loan_number": self.loan.loan_number, "installment_number": 1},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "PENDING")
        self.assertIsNotNone(data["reference"])
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_loan_repay_rejects_already_paid_installment(self):
        self.schedule1.is_paid = True
        self.schedule1.save()
        resp = self.client.post(
            "/api/v1/payments/loans/repay/",
            {"loan_number": self.loan.loan_number, "installment_number": 1},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_loan_repay_rejects_wrong_member(self):
        other_user = User.objects.create_user(email="other1@test.com", username="other1", password="pass", is_active=True)
        other_member = Member.objects.create(
            user=other_user,
            membership_number="MTEST006",
            first_name="Other",
            last_name="Loan",
            phone_number="+255700005566",
            is_verified=True,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(other_user).access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        resp = self.client.post(
            "/api/v1/payments/loans/repay/",
            {"loan_number": self.loan.loan_number, "installment_number": 1},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)


class PaymentTransactionStatusViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="statmem1@test.com", username="statmem1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST007",
            first_name="Status",
            last_name="Member",
            phone_number="+255700007788",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default6", code="DEF6", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        self.tx = PaymentTransaction.objects.create(
            member=self.member,
            transaction_type=PaymentTransaction.Type.OTHER,
            amount=Decimal("1000"),
            currency="TZS",
            status=PaymentTransaction.Status.PENDING,
            idempotency_key="TESTTXKEY123",
        )

    def test_my_payments_lists_members_transactions(self):
        resp = self.client.get("/api/v1/payments/transactions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["status"], "PENDING")

    def test_payment_status_returns_correct_tx(self):
        resp = self.client.get(f"/api/v1/payments/transactions/{self.tx.internal_reference}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["reference"], self.tx.internal_reference)

    def test_payment_status_404_for_other_member(self):
        other_user = User.objects.create_user(email="otherstat1@test.com", username="otherstat1", password="pass", is_active=True)
        other_member = Member.objects.create(
            user=other_user,
            membership_number="MTEST008",
            first_name="Other",
            last_name="Stat",
            phone_number="+255700009900",
            is_verified=True,
        )
        from rest_framework_simplejwt.tokens import RefreshToken
        token = str(RefreshToken.for_user(other_user).access_token)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        resp = self.client.get(f"/api/v1/payments/transactions/{self.tx.internal_reference}/")
        self.assertEqual(resp.status_code, 404)


class WebhookIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="whmem1@test.com", username="whmem1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST009",
            first_name="Webhook",
            last_name="Mem",
            phone_number="+255700011122",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default7", code="DEF7", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        self.group = VikobaGroup.objects.create(name="TestGroup3", area="Arusha", country="Tanzania", created_by=self.member)
        self.group.memberships.create(member=self.member, role="member", shares_count=1)

    def test_full_contribution_flow_via_http(self):
        # Set webhook secret for the test so the view accepts the request
        from unittest.mock import patch
        with patch.object(settings, "SNIPPE_WEBHOOK_SECRET", "test-webhook-secret"):
            # 1. Login
            from rest_framework_simplejwt.tokens import RefreshToken
            token = str(RefreshToken.for_user(self.user).access_token)
            self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
            # 2. Initiate
            resp = self.client.post(
                "/api/v1/payments/contributions/pay/",
                {"group_id": str(self.group.pk), "amount": "25000", "month": "2026-06"},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 201)
            ref = resp.json()["reference"]
            tx = PaymentTransaction.objects.get(internal_reference=ref)
            # 3. Simulate payment.completed webhook
            body = {
                "id": _webhook_event_id(),
                "type": "payment.completed",
                "api_version": "2026-01-25",
                "data": {
                    "reference": tx.provider_reference,
                    "amount": {"value": 25000, "currency": "TZS"},
                    "settlement": {"gross": 25000, "fees": 0, "net": 25000},
                    "channel": {"type": "mobile", "provider": "Vodacom"},
                },
            }
            raw, ts, sig = _signed(body, secret="test-webhook-secret", ts=str(time.time()))
            resp = self.client.post(
                "/api/v1/payments/webhooks/snippe/",
                data=raw,
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE=sig,
                HTTP_X_WEBHOOK_TIMESTAMP=ts,
            )
            self.assertEqual(resp.status_code, 200)
            tx.refresh_from_db()
            self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
            self.account.refresh_from_db()
            self.assertEqual(self.account.balance, Decimal("25000"))
            tx.contribution.refresh_from_db()
            self.assertEqual(tx.contribution.status, GroupContribution.Status.CONFIRMED)

    def test_webhook_rejects_bad_signature(self):
        from unittest.mock import patch
        with patch.object(settings, "SNIPPE_WEBHOOK_SECRET", "test-secret"):
            body = {"id": "evt_bad", "type": "payment.completed", "data": {"reference": "nonexistent"}}
            ts = str(time.time())
            resp = self.client.post(
                "/api/v1/payments/webhooks/snippe/",
                data=json.dumps(body),
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE="totally_wrong_sig",
                HTTP_X_WEBHOOK_TIMESTAMP=ts,
            )
            self.assertIn(resp.status_code, [401, 400])

    def test_webhook_rejects_stale_timestamp(self):
        from unittest.mock import patch
        with patch.object(settings, "SNIPPE_WEBHOOK_SECRET", "test-secret"):
            ts = str(time.time() - 400)
            body = {"id": "evt_stale", "type": "payment.completed", "data": {}}
            sig = hmac.new(b"test-secret", f"{ts}.{json.dumps(body)}".encode(), hashlib.sha256).hexdigest()
            resp = self.client.post(
                "/api/v1/payments/webhooks/snippe/",
                data=json.dumps(body),
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE=sig,
                HTTP_X_WEBHOOK_TIMESTAMP=ts,
            )
            self.assertIn(resp.status_code, [401, 400])


class IdempotencyKeyTests(TestCase):
    def test_same_internal_reference_yields_same_key(self):
        from .services.payment_service import _payment_key
        ref = "VCB-TX-20260101010101-ABC123"
        key1 = _payment_key(ref)
        key2 = _payment_key(ref)
        self.assertEqual(key1, key2)
        self.assertLessEqual(len(key1), 30)


class PaymentReliabilityTests(TestCase):
    """Phase 2: provider events are facts, financial history is never silently
    rewritten, and genuine mismatches surface as RECONCILIATION_REQUIRED."""

    def setUp(self):
        self.user = User.objects.create_user(email="rel@test.com", username="rel1", password="pass", is_active=True)
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTESTREL1",
            first_name="Rel",
            last_name="Test",
            phone_number="+255712345670",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Rel", code="RELPROD", is_active=True)
        self.account = SavingsAccount.objects.create(member=self.member, product=self.product, balance=Decimal("0.00"))
        self.group = VikobaGroup.objects.create(name="RelGroup", area="Dar", country="Tanzania", created_by=self.member)
        self.group.memberships.create(member=self.member, role="member", shares_count=1)

    def _make_tx(self, amount="50000"):
        return initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal(amount),
            month="2026-03",
            phone="+255712345670",
        )

    def _event(self, payload):
        return WebhookEvent.objects.create(
            event_id=_webhook_event_id(),
            event_type="payment.completed",
            payload=payload,
        )

    def test_amount_mismatch_flags_reconciliation_and_never_credits(self):
        tx = self._make_tx()
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 500000, "currency": "TZS"},
            "settlement": {"gross": 500000, "fees": 0, "net": 500000},
            "channel": {"type": "mobile"},
        }
        result = handle_payment_completed(self._event(payload), payload)
        tx.refresh_from_db()
        self.assertEqual(result.pk, tx.pk)
        self.assertEqual(tx.status, PaymentTransaction.Status.RECONCILIATION_REQUIRED)
        self.assertEqual(tx.amount, Decimal("50000"))  # never overwritten
        record = ReconciliationRecord.objects.filter(payment=tx, issue_type=ReconciliationRecord.IssueType.AMOUNT_MISMATCH)
        self.assertTrue(record.exists())
        self.assertEqual(self.account.balance, Decimal("0.00"))
        self.assertEqual(tx.contribution.status, GroupContribution.Status.PENDING)

    def test_currency_mismatch_flags_reconciliation(self):
        tx = self._make_tx()
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 50000, "currency": "KES"},
            "settlement": {"gross": 50000, "fees": 0, "net": 50000},
            "channel": {"type": "mobile"},
        }
        handle_payment_completed(self._event(payload), payload)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.RECONCILIATION_REQUIRED)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                payment=tx, issue_type=ReconciliationRecord.IssueType.CURRENCY_MISMATCH
            ).exists()
        )

    def test_amount_never_overwritten_even_when_provider_differs_slightly(self):
        tx = self._make_tx("33333.34")
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 33333, "currency": "TZS"},
            "settlement": {"gross": 33333, "fees": 0, "net": 33333},
            "channel": {"type": "mobile"},
        }
        handle_payment_completed(self._event(payload), payload)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(tx.amount, Decimal("33333.34"))  # our expectation stands

    def test_provider_fee_journaled_once_and_idempotent(self):
        self._make_tx("20000")
        tx = PaymentTransaction.objects.get(transaction_type=PaymentTransaction.Type.CONTRIBUTION)
        payload = {
            "reference": tx.provider_reference,
            "amount": {"value": 20000, "fees": 1200, "currency": "TZS"},
            "settlement": {"gross": 20000, "fees": 1200, "net": 18800},
            "channel": {"type": "mobile"},
        }
        event = self._event(payload)
        handle_payment_completed(event, payload)
        handle_payment_completed(event, payload)  # replay

        from finance.models import FinancialTransaction

        fee_txs = FinancialTransaction.objects.filter(
            transaction_type=FinancialTransaction.TransactionType.PROVIDER_FEE,
            idempotency_key=f"fee-{tx.internal_reference}",
        )
        self.assertEqual(fee_txs.count(), 1)
        fee_tx = fee_txs.first()
        self.assertEqual(fee_tx.amount, Decimal("1200.00"))
        # Member still received the full expected gross.
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("20000.00"))

    def test_unknown_provider_reference_recorded_and_acked(self):
        payload = {
            "reference": "snp_dev_pay_no_such_ref",
            "amount": {"value": 5000, "currency": "TZS"},
            "settlement": {"gross": 5000, "fees": 0, "net": 5000},
            "channel": {"type": "mobile"},
        }
        self.assertIsNone(handle_payment_completed(self._event(payload), payload))
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                provider_reference="snp_dev_pay_no_such_ref",
                issue_type=ReconciliationRecord.IssueType.UNKNOWN_PROVIDER_TRANSACTION,
            ).exists()
        )

    def test_initiation_timeout_keeps_payment_pending(self):
        from unittest.mock import patch

        from .errors import PaymentError
        from .services.snippe import SnippeError, SnippeProvider

        def _boom(**kwargs):
            raise SnippeError("timed out", code="timeout")

        with patch.object(SnippeProvider, "create_payment", side_effect=_boom):
            with self.assertRaises(PaymentError) as ctx:
                initiate_savings_deposit(member=self.member, amount=Decimal("10000"))
        self.assertEqual(ctx.exception.code, PaymentError.PROVIDER_TIMEOUT)
        tx = PaymentTransaction.objects.get(
            member=self.member, transaction_type=PaymentTransaction.Type.DEPOSIT
        )
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertIsNone(tx.provider_reference)

    def test_payout_timeout_keeps_pending_and_withdrawal_approved(self):
        from unittest.mock import patch

        from .errors import PaymentError
        from .services.snippe import SnippeError, SnippeProvider

        from accounts.models import WithdrawalRequest

        withdrawal = WithdrawalRequest.objects.create(
            member=self.member,
            account=self.account,
            amount=Decimal("10000"),
            status=WithdrawalRequest.Status.APPROVED,
        )

        def _boom(**kwargs):
            raise SnippeError("timed out", code="timeout")

        with patch.object(SnippeProvider, "create_payout", side_effect=_boom):
            with self.assertRaises(PaymentError) as ctx:
                initiate_withdrawal_payout(withdrawal=withdrawal)
        self.assertEqual(ctx.exception.code, PaymentError.PROVIDER_TIMEOUT)
        tx = PaymentTransaction.objects.get(withdrawal=withdrawal)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.APPROVED)


class ReconciliationApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.member_user = User.objects.create_user(
            email="recm@test.com", username="recm", password="pass", is_active=True
        )
        self.member_user.role = User.MEMBER
        self.member_user.save()
        self.finance_user = User.objects.create_user(
            email="recstaff@test.com", username="recstaff", password="pass", is_active=True
        )
        self.finance_user.role = User.FINANCE
        self.finance_user.save()
        self.admin_user = User.objects.create_user(
            email="recadmin@test.com", username="recadmin", password="pass", is_active=True
        )
        self.admin_user.role = User.ADMIN
        self.admin_user.save()
        self.record = ReconciliationRecord.objects.create(
            provider="snippe",
            provider_reference="snp_dev_pay_recon",
            issue_type=ReconciliationRecord.IssueType.AMOUNT_MISMATCH,
            expected_amount=Decimal("5000"),
            actual_amount=Decimal("50000"),
            expected_currency="TZS",
            actual_currency="TZS",
            notes="test mismatch",
        )

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {str(RefreshToken.for_user(user).access_token)}"

    def test_list_requires_staff(self):
        self._auth(self.member_user)
        resp = self.client.get("/api/v1/payments/reconciliation/")
        self.assertEqual(resp.status_code, 403)
        self._auth(self.finance_user)
        resp = self.client.get("/api/v1/payments/reconciliation/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body[0]["id"], self.record.pk)
        self.assertEqual(body[0]["resolution_status"], ReconciliationRecord.ResolutionStatus.OPEN)

    def test_resolve_requires_admin_manager_empty_note_400(self):
        self._auth(self.finance_user)
        resp = self.client.post(
            f"/api/v1/payments/reconciliation/{self.record.pk}/resolve/",
            {"resolution_note": "approved correction"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self._auth(self.admin_user)
        resp = self.client.post(
            f"/api/v1/payments/reconciliation/{self.record.pk}/resolve/",
            {"resolution_note": "  "},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_resolve_writes_audit_and_closes_record(self):
        from finance.models import AuditEvent

        self._auth(self.admin_user)
        resp = self.client.post(
            f"/api/v1/payments/reconciliation/{self.record.pk}/resolve/",
            {"resolution_note": "Provider confirmed real amount; funds posted manually."},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["resolution_status"], ReconciliationRecord.ResolutionStatus.RESOLVED)
        self.record.refresh_from_db()
        self.assertEqual(self.record.resolution_status, ReconciliationRecord.ResolutionStatus.RESOLVED)
        self.assertEqual(self.record.resolved_by_id, self.admin_user.pk)
        self.assertTrue(AuditEvent.objects.filter(action="payment.reconciliation.resolved").exists())
        # Already resolved → cannot resolve again.
        resp = self.client.post(
            f"/api/v1/payments/reconciliation/{self.record.pk}/resolve/",
            {"resolution_note": "again"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)