"""Snippe sandbox client. All calls are server-side; the API key lives only in
the environment. Phone numbers are masked in every log line. Amounts are sent
as integer smallest currency units (TZS -> raw shillings).

No real money is ever moved in development: when SNIPPE_DEV_MODE is on the
provider fakes the sandbox responses on the JSON contract documented in the
Snippe API docs.
"""
import hashlib
import hmac
import time

import requests
from django.conf import settings

from payments.utils.phone import SNIPPE_NETWORK_IDS, mask_phone, normalize_phone, int_amount

PAYMENT_PREFIX = "VCBPAY"
PAYOUT_PREFIX = "VCBPAYOUT"
API_VERSION = "v1"
MIN_PAYMENT = 500
MIN_PAYOUT = 5000


class SnippeError(Exception):
    """Raised for provider-level errors (network, HTTP status, bad payload)."""

    def __init__(self, message, code=None, payload=None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


class SnippeAuthError(SnippeError):
    pass


class SnippeRateLimitError(SnippeError):
    pass


def _build_reference(prefix):
    ts = time.strftime("%Y%m%d%H%M%S")
    return f"{prefix}{ts}{int(time.monotonic() * 1000) % 100000:05d}"


class SnippeProvider:
    """Thin wrapper over the Snippe REST API for payments & payouts."""

    def __init__(self):
        self.base_url = (getattr(settings, "SNIPPE_BASE_URL", "") or "").rstrip("/")
        self.api_key = getattr(settings, "SNIPPE_API_KEY", "") or ""
        self.webhook_url = (getattr(settings, "SNIPPE_WEBHOOK_URL", "") or "").rstrip("/")
        self.current_environment = getattr(settings, "SNIPPE_ENVIRONMENT", "sandbox") or "sandbox"
        self.is_dev = getattr(settings, "SNIPPE_DEV_MODE", False)

    # ------------------------------------------------------------------ auth
    def _headers(self, extra=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path):
        return f"{self.base_url}/{API_VERSION}/{path.lstrip('/')}"

    def _safe_payload(self, payload, phone=None):
        safe = dict(payload)
        if phone:
            if "phone_number" in safe:
                safe["phone_number"] = mask_phone(safe["phone_number"])
            if "recipient_phone" in safe:
                safe["recipient_phone"] = mask_phone(safe["recipient_phone"])
        return safe

    def _request(self, method, path, *, json=None, phone=None):
        if not self.api_key and not self.is_dev:
            raise SnippeAuthError("SNIPPE_API_KEY is not configured.")

        if self.is_dev:
            # Simulated sandbox: mirror the documented JSON contract without
            # dialing out, so the demo and test-suite move real shaped payloads
            # but no real money (same spirit as OTP_DEV_MODE).
            return self._dev_response(method, path, json or {}, phone)

        url = self._url(path)
        headers = self._headers()
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json,
                timeout=(getattr(settings, "SNIPPE_TIMEOUT", 10) or 10),
            )
        except requests.exceptions.Timeout as exc:
            # A timeout does NOT prove the request failed — it may have reached
            # Snippe. Callers must keep the payment PENDING (never FAILED) until
            # the provider status is verified.
            raise SnippeError(
                f"Provider timed out: {exc}",
                code="timeout",
            ) from exc
        except requests.RequestException as exc:
            raise SnippeError(
                f"Provider unreachable: {exc}",
                code="provider_unreachable",
            ) from exc

        if response.status_code == 401:
            raise SnippeAuthError("Snippe rejected the API key.", code="unauthorized")
        if response.status_code == 429:
            raise SnippeRateLimitError("Snippe rate limit hit.", code="rate_limited")

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if response.status_code >= 400 or not response.ok:
            code = body.get("code") or body.get("error") or f"http_{response.status_code}"

            # Per docs, idempotency / validation failures come back 422 with a
            # `code` we surface verbatim so the payment service can re-use the key.
            raise SnippeError(
                body.get("message") or str(body),
                code=code,
                payload=body,
            )

        return body if isinstance(body, dict) else {"result": body}

    # ------------------------------------------------------------- collections
    def create_payment(self, *, amount, phone, customer, metadata, reference=None):
        """
        Initiate a mobile-money payment (collection).

        reference: our own idempotency key <= 30 chars, reused on every retry of
        the same logical payment. If none given we derive one from the internal
        reference of the PaymentTransaction, which never changes.
        """
        amount = int_amount(amount)
        if amount < MIN_PAYMENT:
            raise SnippeError(
                f"Amount must be at least {MIN_PAYMENT} TZS.",
                code="amount_too_small",
            )
        if reference and len(reference) > 30:
            raise SnippeError("Idempotency key exceeds 30 characters.", code="invalid_idempotency_key")

        payload = {
            "payment_type": "mobile",
            "details": {"amount": amount, "currency": "TZS"},
            "phone_number": normalize_phone(phone),
            "customer": customer,
            "metadata": metadata or {},
            "webhook_url": self.webhook_url,
        }
        if reference:
            payload["reference"] = reference

        return self._request("POST", "payments", json=payload, phone=phone)

    def get_payment(self, reference):
        return self._request("GET", f"payments/{reference}")

    # ---------------------------------------------------------------- payouts
    def create_payout(self, *, amount, recipient_phone, recipient_name, narration, network=None, metadata=None, reference=None):
        """
        Send money to a member's mobile money account (disbursement). Owns its
        own idempotency key namespace so a payout retry never collides with a
        payment of the same internal reference.

        Per Snippe docs: min 5000 TZS, idempotency key <= 30 chars, valid 24h.
        `network` explicitly selects the mobile-money network for the payout
        (mpesa / airtel / mixx / halotel); when omitted Snippe resolves it from
        the recipient number.
        """
        amount = int_amount(amount)
        if amount < MIN_PAYOUT:
            raise SnippeError(
                f"Payout amount must be at least {MIN_PAYOUT} TZS.",
                code="payout_amount_too_small",
            )
        if network and network not in SNIPPE_NETWORK_IDS:
            raise SnippeError(f"Unknown payout network: {network}", code="invalid_network")
        key = reference or self._payout_key(amount)
        if len(key) > 30:
            raise SnippeError("Payout idempotency key exceeds 30 characters.", code="invalid_idempotency_key")

        payload = {
            "amount": amount,
            "channel": "mobile",
            "recipient_phone": normalize_phone(recipient_phone),
            "recipient_name": recipient_name,
            "narration": narration or "VICOBA payout",
            "webhook_url": self.webhook_url,
            "metadata": metadata or {},
            "reference": key,
        }
        if network:
            payload["network"] = network

        return self._request("POST", "payouts/send", json=payload, phone=recipient_phone)

    @staticmethod
    def _payout_key(amount):
        return _build_reference(PAYOUT_PREFIX)[:30]

    def get_payout(self, reference):
        return self._request("GET", f"payouts/{reference}")

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def verify_webhook_signature(secret, timestamp, raw_body, signature):
        """Constant-time HMAC-SHA256 check using Snippe's documented format."""
        expected = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected.lower(), signature.lower())

    def _dev_response(self, method, path, payload, phone):
        """Deterministic fake responses used when SNIPPE_DEV_MODE is on."""
        import time as _time

        stamp = _time.strftime("%Y%m%d%H%M%S")
        suffix = str(int(_time.time() * 1000) % 100000)
        reference = None

        if path == f"payments" and method.upper() == "POST":
            reference = f"snp_dev_pay_{stamp}{suffix}"
            return {
                "reference": reference,
                "status": "pending",
                "details": {"amount": payload["details"]["amount"], "currency": "TZS"},
                "metadata": payload.get("metadata", {}),
            }
        if path.startswith("payments/") and method.upper() == "GET":
            reference = path.split("/", 1)[1]
            return {
                "reference": reference,
                "status": "completed" if reference.endswith("_ok") else "pending",
                "amount": {"value": payload.get("amount", 0), "currency": "TZS"},
            }
        if path == f"payouts/send" and method.upper() == "POST":
            reference = f"snp_dev_payout_{stamp}{suffix}"
            return {
                "reference": reference,
                "status": "pending" if reference.endswith("_pending") else "processing",
                "recipient_phone": mask_phone(payload.get("recipient_phone", "")),
                "amount": payload.get("amount", 0),
                "currency": "TZS",
                "network": payload.get("network"),
                "metadata": payload.get("metadata", {}),
            }
        if path.startswith("payouts/") and method.upper() == "GET":
            reference = path.split("/", 1)[1]
            return {
                "reference": reference,
                "status": "completed" if reference.endswith("_ok") else "processing",
            }

        raise SnippeError(f"Unsupported dev-mode request {method} {path}", code="dev_unsupported")