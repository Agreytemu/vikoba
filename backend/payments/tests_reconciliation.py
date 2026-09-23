"""Phase 5 STEP 4: reconciliation exception handling tests.

Covers the audit's previously-dead issue types plus the escape hatch:
- RECONCILIATION_REQUIRED payments can no longer be silently downgraded to
  FAILED by a later failure report (payments and payouts).
- A second completion event for an already-settled payment creates a
  DUPLICATE_PROVIDER_TRANSACTION record instead of double-crediting.
- Duplicate webhook delivery (same event id twice) surfaces as
  ALREADY_PROCESSED_EVENT.
- The reconcile command turns provider lookup failures into PROVIDER_ERROR
  records, detects missed webhook deliveries (MISSING_WEBHOOK) and settled
  payments that never reached the ledger (MISSING_INTERNAL_TRANSACTION).
"""
import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from accounts.models import SavingsAccount, SavingsProduct
from groups.models import VikobaGroup
from members.models import Member

from .models import PaymentTransaction, ReconciliationRecord, WebhookEvent
from .services.payment_service import (
    handle_payment_completed,
    handle_payment_failed,
    handle_payout_failed,
    initiate_contribution_payment,
)
from .services.snippe import SnippeError, SnippeProvider

User = get_user_model()
WEBHOOK_SECRET = "test-webhook-secret"
_ID_SEQ = {"n": 0}


def _webhook_event_id():
    _ID_SEQ["n"] += 1
    return f"evt_{_ID_SEQ['n']}_{int(time.time() * 1000)}"


def _signed(body_dict, secret=WEBHOOK_SECRET, ts=None):
    raw = json.dumps(body_dict, separators=(",", ":"))
    t = ts or str(time.time())
    sig = hmac.new(secret.encode(), f"{t}.{raw}".encode(), hashlib.sha256).hexdigest()
    return raw, t, sig


class ReconciliationBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="recon1@test.com", username="recon1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTESTREC01",
            first_name="Rec",
            last_name="People",
            phone_number="+255711223344",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="TestGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        self.group.memberships.create(member=self.member, role="member", shares_count=1)

    def _pending(self, amount="25000.00", ref=None, type_=PaymentTransaction.Type.CONTRIBUTION):
        _ID_SEQ["n"] += 1
        return PaymentTransaction.objects.create(
            member=self.member,
            group=self.group,
            transaction_type=type_,
            amount=Decimal(amount),
            currency="TZS",
            status=PaymentTransaction.Status.PENDING,
            provider_reference=ref or f"snp_dev_pay_recon_{_ID_SEQ['n']}",
            idempotency_key=f"recon-key-{type_}-{_ID_SEQ['n']}",
        )

    def _completed_payload(self, tx, value):
        return {
            "reference": tx.provider_reference,
            "amount": {"value": value, "currency": "TZS"},
            "settlement": {"gross": value, "fees": 0, "net": value},
            "channel": {"type": "mobile"},
        }


class ReconciliationRequiredGuardTests(ReconciliationBase):
    def test_failed_report_keeps_reconciliation_required(self):
        tx = self._pending()
        tx.require_reconciliation(reason="amount mismatch")
        event = WebhookEvent.objects.create(
            event_id=_webhook_event_id(), event_type="payment.failed", payload={}
        )
        handle_payment_failed(event, {"reference": tx.provider_reference, "message": "late failure"})
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.RECONCILIATION_REQUIRED)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                payment=tx, issue_type=ReconciliationRecord.IssueType.PROVIDER_ERROR
            ).exists()
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("0.00"))

    def test_payout_failed_report_keeps_reconciliation_required(self):
        tx = self._pending(
            type_=PaymentTransaction.Type.WITHDRAWAL, ref="snp_dev_payout_recon"
        )
        tx.require_reconciliation(reason="payout under review")
        event = WebhookEvent.objects.create(
            event_id=_webhook_event_id(), event_type="payout.failed", payload={}
        )
        handle_payout_failed(event, {"reference": tx.provider_reference, "message": "late failure"})
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.RECONCILIATION_REQUIRED)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                payment=tx, issue_type=ReconciliationRecord.IssueType.PROVIDER_ERROR
            ).exists()
        )


class DuplicateCompletionRecordTests(ReconciliationBase):
    def test_second_completion_event_recorded_not_double_credited(self):
        tx = self._pending(amount="50000.00")
        first = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload={})
        handle_payment_completed(first, self._completed_payload(tx, 50000))
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.account.refresh_from_db()
        balance_after_first = self.account.balance

        second = WebhookEvent.objects.create(event_id=_webhook_event_id(), event_type="payment.completed", payload={})
        handle_payment_completed(second, self._completed_payload(tx, 50000))
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                payment=tx,
                issue_type=ReconciliationRecord.IssueType.DUPLICATE_PROVIDER_TRANSACTION,
                event_id=second.event_id,
            ).exists()
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, balance_after_first)

    def test_synthetic_poll_replay_is_not_recorded_as_duplicate(self):
        tx = self._pending(amount="30000.00")
        first = WebhookEvent.objects.create(event_id="evt_first_poll", event_type="payment.completed", payload={})
        handle_payment_completed(first, self._completed_payload(tx, 30000))
        synthetic = WebhookEvent.objects.create(
            event_id=f"recon-{tx.internal_reference}", event_type="payment.completed", payload={}
        )
        handle_payment_completed(synthetic, self._completed_payload(tx, 30000))
        self.assertFalse(
            ReconciliationRecord.objects.filter(
                payment=tx,
                issue_type=ReconciliationRecord.IssueType.DUPLICATE_PROVIDER_TRANSACTION,
            ).exists()
        )


class AlreadyProcessedEventTests(ReconciliationBase):
    def test_duplicate_webhook_delivery_records_already_processed_event(self):
        self.client = Client()
        tx = self._pending(amount="20000.00")
        body = {
            "id": "evt_dupe_recon",
            "type": "payment.completed",
            "api_version": "2026-01-25",
            "data": {
                "reference": tx.provider_reference,
                "amount": {"value": 20000, "currency": "TZS"},
                "settlement": {"gross": 20000, "fees": 0, "net": 20000},
                "channel": {"type": "mobile"},
            },
        }
        with patch.object(settings, "SNIPPE_WEBHOOK_SECRET", WEBHOOK_SECRET):
            raw, ts, sig = _signed(body)
            headers = {"HTTP_X_WEBHOOK_SIGNATURE": sig, "HTTP_X_WEBHOOK_TIMESTAMP": ts}
            first = self.client.post(
                "/api/v1/payments/webhooks/snippe/",
                data=raw,
                content_type="application/json",
                **headers,
            )
            self.assertEqual(first.status_code, 200)
            second = self.client.post(
                "/api/v1/payments/webhooks/snippe/",
                data=raw,
                content_type="application/json",
                **headers,
            )
            self.assertEqual(second.status_code, 200)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                provider_reference=tx.provider_reference,
                issue_type=ReconciliationRecord.IssueType.ALREADY_PROCESSED_EVENT,
            ).exists()
        )


class ReconcileCommandExceptionTests(ReconciliationBase):
    def test_provider_error_becomes_provider_error_record(self):
        tx = self._pending()
        with patch.object(SnippeProvider, "get_payment", side_effect=SnippeError("boom")):
            call_command("reconcile_payments", "--payments")
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                provider_reference=tx.provider_reference,
                issue_type=ReconciliationRecord.IssueType.PROVIDER_ERROR,
            ).exists()
        )
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)

    def test_polled_completion_records_missing_webhook_and_posts(self):
        tx = initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal("40000"),
            month="2026-07",
            phone="+255712345678",
        )
        with patch.object(
            SnippeProvider,
            "get_payment",
            return_value={
                "reference": tx.provider_reference,
                "status": "completed",
                "amount": {"value": 40000, "currency": "TZS"},
            },
        ):
            call_command("reconcile_payments", "--payments")
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                provider_reference=tx.provider_reference,
                issue_type=ReconciliationRecord.IssueType.MISSING_WEBHOOK,
            ).exists()
        )
        self.assertFalse(
            ReconciliationRecord.objects.filter(
                provider_reference=tx.provider_reference,
                issue_type=ReconciliationRecord.IssueType.MISSING_INTERNAL_TRANSACTION,
            ).exists()
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("40000.00"))

    def test_polled_subscription_records_missing_internal_transaction(self):
        tx = self._pending(
            amount="15000.00",
            type_=PaymentTransaction.Type.SUBSCRIPTION,
            ref="snp_dev_sub_recon",
        )
        with patch.object(
            SnippeProvider,
            "get_payment",
            return_value={
                "reference": tx.provider_reference,
                "status": "completed",
                "amount": {"value": 15000, "currency": "TZS"},
            },
        ):
            call_command("reconcile_payments", "--payments")
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)
        self.assertTrue(
            ReconciliationRecord.objects.filter(
                provider_reference=tx.provider_reference,
                issue_type=ReconciliationRecord.IssueType.MISSING_INTERNAL_TRANSACTION,
            ).exists()
        )