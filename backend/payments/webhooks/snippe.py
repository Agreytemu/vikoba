"""Snippe webhook verification & dispatch.

Verified signature + timestamp freshness before we ever touch a database row.
The event is persisted with a UNIQUE event id so at-least-once delivery from
Snippe cannot double-process a completed payment.
"""
import hashlib
import hmac
import logging

from django.conf import settings
from django.utils import timezone

from payments.models import PaymentTransaction, WebhookEvent
from payments.services.payment_service import (
    handle_payment_completed,
    handle_payment_failed,
    handle_payout_completed,
    handle_payout_failed,
)

logger = logging.getLogger("payments")


class WebhookVerificationError(Exception):
    pass


class WebhookVerifier:
    def __init__(self, signing_key=None):
        self.signing_key = signing_key or getattr(settings, "SNIPPE_WEBHOOK_SECRET", "")

    def verify(self, signature_header, timestamp_header, raw_body, max_age_seconds=300):
        """Raises WebhookVerificationError on any failure. Returns None on success."""
        if not signature_header or not timestamp_header:
            raise WebhookVerificationError("Missing signature or timestamp header.")
        if not self.signing_key:
            raise WebhookVerificationError("Webhook secret not configured.")

        try:
            timestamp = float(timestamp_header)
            age = timezone.now().timestamp() - timestamp
        except (TypeError, ValueError):
            raise WebhookVerificationError("Invalid webhook timestamp.")

        if age > max_age_seconds:
            raise WebhookVerificationError("Webhook is stale (timestamp too old).")

        expected = hmac.new(
            self.signing_key.encode("utf-8"),
            f"{timestamp_header}.{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature_header):
            raise WebhookVerificationError("Signature mismatch.")


class WebhookDispatcher:
    """Routes a verified event to the correct idempotent handler."""

    EVENT_PAYMENT_COMPLETED = "payment.completed"
    EVENT_PAYMENT_FAILED = "payment.failed"
    EVENT_PAYMENT_VOIDED = "payment.voided"
    EVENT_PAYMENT_EXPIRED = "payment.expired"
    EVENT_PAYOUT_COMPLETED = "payout.completed"
    EVENT_PAYOUT_FAILED = "payout.failed"
    EVENT_PAYOUT_REVERSED = "payout.reversed"

    def __init__(self):
        self._handlers = {
            self.EVENT_PAYMENT_COMPLETED: handle_payment_completed,
            self.EVENT_PAYMENT_FAILED: handle_payment_failed,
            self.EVENT_PAYMENT_VOIDED: handle_payment_failed,
            self.EVENT_PAYMENT_EXPIRED: handle_payment_failed,
            self.EVENT_PAYOUT_COMPLETED: handle_payout_completed,
            self.EVENT_PAYOUT_FAILED: handle_payout_failed,
            self.EVENT_PAYOUT_REVERSED: handle_payout_failed,
        }

    def dispatch(self, event: WebhookEvent, payload=None):
        handler = self._handlers.get(event.event_type)
        if handler is None:
            logger.warning("Unhandled webhook event %s (%s)", event.event_type, event.event_id)
            return None
        # Snippe envelope: {"id","type","data":{...}} — handlers receive `data`.
        body = payload or event.payload
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            body = body["data"]
        result = handler(event, body)
        event.processed = True
        event.save(update_fields=["processed"])
        return result