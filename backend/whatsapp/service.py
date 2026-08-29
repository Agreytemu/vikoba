import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class BridgeError(Exception):
    """The WhatsApp bridge could not be reached or rejected the request."""


def bridge_configured():
    return bool(getattr(settings, "WHATSAPP_BRIDGE_URL", ""))


def _bridge_call(method, path, payload=None, timeout=8):
    base = getattr(settings, "WHATSAPP_BRIDGE_URL", "").rstrip("/")
    if not base:
        raise BridgeError("WHATSAPP_BRIDGE_URL is not configured")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base + path, data=data, method=method,
        headers={
            "Content-Type": "application/json",
            "x-bridge-token": getattr(settings, "WHATSAPP_BRIDGE_TOKEN", ""),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8") or "{}"
            return json.loads(body)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise BridgeError(f"bridge {method} {path} -> {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise BridgeError(f"bridge unreachable: {error}") from error


def start_session(session):
    """Ask the bridge to create/start the session (must exist in our DB first)."""
    if not bridge_configured():
        return None
    try:
        return _bridge_call("POST", "/sessions", {
            "id": session.session_id,
            "display_name": session.display_name,
        })
    except BridgeError as error:
        logger.warning("start_session %s failed: %s", session.session_id, error)
        return None


def session_status(session, want_pairing=False):
    """Poll the bridge for a session; returns the status dict.

    ``pairing_code`` is only included when explicitly requested (never on list).
    """
    if not bridge_configured():
        return {"status": "disconnected", "exists": False, "phone": ""}
    try:
        payload = _bridge_call("GET", f"/sessions/{session.session_id}")
    except BridgeError as error:
        logger.warning("session_status %s failed: %s", session.session_id, error)
        return {"status": "error", "exists": False, "phone": ""}
    if not want_pairing:
        payload.pop("pairing_code", None)
    return payload


def pair_session(session_id, phone_number):
    """Ask the bridge for a WhatsApp pairing code to type into the phone.

    Baileys can also emit a QR code for the standard WhatsApp device-link flow;
    the frontend polls the bridge for that QR and connects when it is scanned.
    """
    if not bridge_configured():
        return {"ok": False, "error": "bridge_not_configured"}
    try:
        return _bridge_call("POST", f"/sessions/{session_id}/pair", {
            "phone": phone_number,
        })
    except BridgeError as error:
        logger.warning("pair_session %s failed: %s", session_id, error)
        return {"ok": False, "error": str(error)}


def send_whatsapp(session_id, phone, text):
    """Deliver a text message via an already-paired session.

    Returns a dict with `ok`; missing/undeliverable sessions simply return
    ok: False so callers can fall back to other channels without raising.
    """
    if not bridge_configured():
        return {"ok": False, "error": "bridge_not_configured"}
    try:
        return _bridge_call("POST", f"/sessions/{session_id}/send", {
            "to": phone, "text": text,
        })
    except BridgeError as error:
        logger.warning("send_whatsapp via %s to %s failed: %s", session_id, phone, error)
        return {"ok": False, "error": str(error)}


def send_bulk(session_id, phones, text):
    if not bridge_configured():
        return {"ok": False, "error": "bridge_not_configured", "sent": 0, "failed": []}
    try:
        return _bridge_call("POST", f"/sessions/{session_id}/send-bulk", {
            "to": phones, "text": text,
        })
    except BridgeError as error:
        logger.warning("send_bulk via %s failed: %s", session_id, error)
        return {"ok": False, "error": str(error), "sent": 0, "failed": []}


def list_bridge_sessions():
    """All sessions currently known to the bridge (id -> status map)."""
    if not bridge_configured():
        return {}
    try:
        return _bridge_call("GET", "/sessions")
    except BridgeError as error:
        logger.warning("list_bridge_sessions failed: %s", error)
        return {}


def default_admin_session():
    """Best admin-owned session to send system messages (OTP etc.) from."""
    return (
        WhatsAppSession.objects
        .filter(owner_type=WhatsAppSession.OwnerType.ADMIN, status="connected")
        .order_by("-is_primary", "-updated_at")
        .first()
    )


def deliver_otp(member, phone_number, code):
    """Send the phone-verification OTP over WhatsApp when a device is paired.

    Returns the channel actually used ("whatsapp"/"none") — never raises.
    """
    session = default_admin_session()
    if not session:
        return "none"
    message = (
        f"Your Vikoba Kidigitali verification code is {code}.\n"
        "It expires in 10 minutes. Do not share it with anyone."
    )
    result = send_whatsapp(session.session_id, phone_number, message)
    if result.get("ok"):
        return "whatsapp"
    return "none"


def deliver_receipt(contribution):
    """Send a payment receipt from the group chair's device (or admin device).

    Called when a staff member confirms a contribution; failures are logged and
    must never block the confirmation itself.
    """
    group = contribution.group
    session = (
        WhatsAppSession.objects
        .filter(owner_type=WhatsAppSession.OwnerType.CHAIR, group=group, status="connected")
        .order_by("-is_primary", "-updated_at")
        .first()
    )
    if session is None:
        session = default_admin_session()
    if session is None:
        logger.info("No connected WhatsApp session; skipping receipt for %s", contribution)
        return False

    payer = contribution.member
    amount = f"{contribution.amount:,.0f}"
    message = (
        f"Vikoba Kidigitali - Contribution receipt\n"
        f"Group: {group.name}\n"
        f"Amount: KSh {amount}\n"
        f"Month: {contribution.month}\n"
        + (f"Reference: {contribution.reference}\n" if contribution.reference else "")
        + f"Status: {contribution.status}\n"
        f"Member: {payer.first_name} {payer.last_name}"
    )
    if not payer.phone_number:
        return False
    result = send_whatsapp(session.session_id, payer.phone_number, message)
    return bool(result.get("ok"))


# Imported at the bottom to avoid a circular import with the models module.
from .models import WhatsAppSession  # noqa: E402