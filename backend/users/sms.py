import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(to, message):
    """Send an SMS via Twilio when configured; otherwise log and return False.

    Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM to enable.
    """
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    sender = getattr(settings, "TWILIO_FROM", "")
    if not (sid and token and sender):
        logger.warning("SMS not configured; skipping message to %s", to)
        return False
    try:
        from twilio.rest import Client

        Client(sid, token).messages.create(to=to, from_=sender, body=message)
        return True
    except Exception:  # pragma: no cover - provider failures are runtime only
        logger.exception("SMS delivery failed to %s", to)
        return False