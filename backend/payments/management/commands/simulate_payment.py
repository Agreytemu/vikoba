"""DEV ONLY — simulate a verified Snippe webhook for one pending payment.

The provider is faked in SNIPPE_DEV_MODE (it never dials out), so there is no
real USSD push to approve. This command applies the exact same idempotent
handlers a ``payment.completed`` / ``payment.failed`` webhook would, letting the
demo walk through the whole checkout -> confirmed -> subscription activated flow
without a Snippe account. It is intentionally unusable outside local dev.

Usage:
    python manage.py simulate_payment VCB-TX-... [--status failed]
"""
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from payments.models import PaymentTransaction, WebhookEvent
from payments.services.payment_service import (
    handle_payment_completed,
    handle_payment_failed,
)


class Command(BaseCommand):
    help = "DEV ONLY: drive a pending payment to completed/failed as if a Snippe webhook arrived."

    def add_arguments(self, parser):
        parser.add_argument("internal_reference", type=str)
        parser.add_argument(
            "--status",
            default="completed",
            choices=["completed", "failed"],
            help="Outcome to simulate (default: completed).",
        )

    def handle(self, *args, **options):
        if settings.SNIPPE_DEV_MODE is not True:
            raise CommandError(
                "simulate_payment is a development-only command. "
                "Set SNIPPE_DEV_MODE=true to use it."
            )

        reference = options["internal_reference"]
        outcome = options["status"]

        tx = PaymentTransaction.objects.filter(internal_reference=reference).first()
        if tx is None:
            raise CommandError(f"No payment found with reference {reference}.")

        if tx.status == PaymentTransaction.Status.SUCCESS:
            self.stdout.write(self.style.WARNING(f"{reference} is already SUCCESS — nothing to do."))
            return
        if not tx.provider_reference:
            raise CommandError(f"{reference} has no provider reference yet.")

        suffix = uuid.uuid4().hex[:12]
        if outcome == "failed":
            event = WebhookEvent.objects.create(
                event_id=f"sim-{tx.internal_reference}-fail-{suffix}",
                event_type="payment.failed",
                api_version="v1",
                payload={"reference": tx.provider_reference, "failure_reason": "simulated user decline"},
                processed=False,
            )
            handler = handle_payment_failed
            handler(event, {
                "reference": tx.provider_reference,
                "failure_reason": "simulated user decline",
            })
            self.stdout.write(self.style.SUCCESS(
                f"{reference} -> FAILED (subscription left inactive)."
            ))
            return

        event = WebhookEvent.objects.create(
            event_id=f"sim-{tx.internal_reference}-ok-{suffix}",
            event_type="payment.completed",
            api_version="v1",
            payload={"reference": tx.provider_reference},
            processed=False,
        )
        handler = handle_payment_completed
        handler(event, {
            "reference": tx.provider_reference,
            "amount": {
                "value": int(tx.amount),
                "currency": tx.currency or "TZS",
                "fees": 0,
                "net": int(tx.amount),
            },
            "settlement": {"currency": tx.currency or "TZS"},
            "channel": "mobile",
        })
        self.stdout.write(self.style.SUCCESS(
            f"{reference} -> SUCCESS (subscription activated)."
        ))