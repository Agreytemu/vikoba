from decimal import Decimal

from django.core.management.base import BaseCommand

from payments.models import PaymentTransaction, ReconciliationRecord, WebhookEvent
from payments.services.payment_service import (
    handle_payment_completed,
    handle_payment_failed,
    handle_payout_completed,
    handle_payout_failed,
)
from payments.services.snippe import SnippeProvider


class Command(BaseCommand):
    """Reconcile pending Snippe payments against the provider.

    Normally webhooks drive state, but a missed delivery must not leave a member
    with a PENDING payment forever. This pulls the latest status per reference and
    applies the same idempotent handlers the webhook would have. Safe to run
    repeatedly; anything already SUCCESS is skipped. Every genuine mismatch is
    recorded as a ReconciliationRecord instead of being silently corrected.
    """

    help = "Pull latest Snippe status for pending payments and reconcile."

    def add_arguments(self, parser):
        parser.add_argument(
            "--payments", action="store_true", help="Reconcile mobile-money collections."
        )
        parser.add_argument(
            "--payouts", action="store_true", help="Reconcile mobile-money payouts."
        )

    def handle(self, *args, **options):
        reconcile_payments = options["payments"] or not (options["payments"] or options["payouts"])
        reconcile_payouts = options["payouts"]

        provider = SnippeProvider()
        reconciled = {"payments": 0, "payouts": 0, "failed": 0}

        if reconcile_payments:
            pending = PaymentTransaction.objects.filter(
                status__in=[
                    PaymentTransaction.Status.PENDING,
                    PaymentTransaction.Status.RECONCILIATION_REQUIRED,
                ],
                transaction_type__in=[
                    PaymentTransaction.Type.CONTRIBUTION,
                    PaymentTransaction.Type.DEPOSIT,
                    PaymentTransaction.Type.LOAN_REPAYMENT,
                    PaymentTransaction.Type.SUBSCRIPTION,
                ],
            ).exclude(provider_reference__isnull=True)
            for tx in pending:
                self._reconcile(
                    tx, provider=provider, kind="payment", stats=reconciled
                )

        if reconcile_payouts:
            pending = PaymentTransaction.objects.filter(
                status__in=[
                    PaymentTransaction.Status.PENDING,
                    PaymentTransaction.Status.PROCESSING,
                    PaymentTransaction.Status.RECONCILIATION_REQUIRED,
                ],
                transaction_type=PaymentTransaction.Type.WITHDRAWAL,
            )
            for tx in pending:
                self._reconcile(tx, provider=provider, kind="payout", stats=reconciled)

        self.stdout.write(self.style.SUCCESS(
            f"Reconciled {reconciled['payments']} payments, "
            f"{reconciled['payouts']} payouts; {reconciled['failed']} failed."
        ))

    def _reconcile(self, tx, *, provider, kind, stats):
        if not tx.provider_reference:
            return
        fetcher = provider.get_payment if kind == "payment" else provider.get_payout
        try:
            status_body = fetcher(tx.provider_reference)
        except Exception:
            self.stderr.write(f"Skipped {tx.internal_reference}: provider error")
            return

        raw_status = str(status_body.get("status", "")).lower()
        if raw_status in ("completed", "successful", "success", "paid"):
            handler = handle_payment_completed if kind == "payment" else handle_payout_completed
            event, _ = WebhookEvent.objects.get_or_create(
                event_id=f"recon-{tx.internal_reference}",
                defaults={
                    "event_type": f"{kind}.completed",
                    "payload": {"reference": tx.provider_reference, **status_body},
                    "processed": True,
                },
            )
            handler(event, {"reference": tx.provider_reference, **status_body})
            stats["payments" if kind == "payment" else "payouts"] += 1
            self.stdout.write(f"{tx.internal_reference} -> completed")
        elif raw_status in ("failed", "voided", "expired", "rejected", "cancelled"):
            handler = handle_payment_failed if kind == "payment" else handle_payout_failed
            event, _ = WebhookEvent.objects.get_or_create(
                event_id=f"recon-{tx.internal_reference}:fail",
                defaults={
                    "event_type": f"{kind}.failed",
                    "payload": {"reference": tx.provider_reference, **status_body},
                    "processed": True,
                },
            )
            handler(event, {"reference": tx.provider_reference, **status_body})
            stats["failed"] += 1
            self.stdout.write(f"{tx.internal_reference} -> failed")
        elif raw_status in ("pending", "processing", "initiated", "in_progress"):
            if tx.status != PaymentTransaction.Status.RECONCILIATION_REQUIRED:
                ReconciliationRecord.objects.get_or_create(
                    provider=tx.provider,
                    provider_reference=tx.provider_reference or "",
                    issue_type=ReconciliationRecord.IssueType.DELAYED_CONFIRMATION,
                    defaults={
                        "payment": tx,
                        "internal_reference": tx.internal_reference,
                        "expected_amount": tx.amount,
                        "expected_currency": tx.currency or "TZS",
                        "actual_status": raw_status,
                        "notes": "Provider still reports the payment as in progress.",
                    },
                )
            self.stdout.write(f"{tx.internal_reference} -> still {raw_status}")
        else:
            # Provider reports an unexpected terminal state we don't model.
            ReconciliationRecord.objects.get_or_create(
                provider=tx.provider,
                provider_reference=tx.provider_reference or "",
                issue_type=ReconciliationRecord.IssueType.STATUS_MISMATCH,
                defaults={
                    "payment": tx,
                    "internal_reference": tx.internal_reference,
                    "expected_amount": tx.amount,
                    "expected_status": tx.status,
                    "actual_status": raw_status,
                    "notes": "Provider returned a status this system does not model.",
                },
            )
            self.stdout.write(f"{tx.internal_reference} -> {raw_status} (unexpected)")