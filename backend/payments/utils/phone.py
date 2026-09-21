"""Phone formatting & network helpers. The rest of the platform stores members
with +255..., while Snippe accepts both 255... and +255...; everything outbound
goes through this module so a raw 0-prefixed or local-format number is never
sent."""

# Snippe mobile-money networks supported for collections & payouts (TZS).
# Stable IDs mirror the frontend `SNIPPE_NETWORKS` registry.
SNIPPE_NETWORKS = {
    "mpesa": {"name": "M-Pesa", "operator": "Vodacom"},
    "airtel": {"name": "Airtel Money", "operator": "Airtel"},
    "mixx": {"name": "Mixx by Yas", "operator": "Yas"},
    "halotel": {"name": "Halotel", "operator": "Halotel"},
}
# The accepted network IDs (payouts / collections). Kept as a module-level set
# so services can validate a client-chosen network without hardcoding strings.
SNIPPE_NETWORK_IDS = frozenset(SNIPPE_NETWORKS)

# Best-effort Tanzanian number prefixes -> Snippe network. Snippe itself
# resolves the real operator from the number; this only drives pre-selection and
# the phone-verification badge.
PREFIX_TO_NETWORK = {
    "74": "mpesa",  # Vodacom
    "75": "mpesa",  # Vodacom
    "76": "mpesa",  # Vodacom
    "77": "mpesa",  # Vodacom
    "67": "airtel",  # Airtel
    "78": "airtel",  # Airtel
    "68": "mixx",  # Mixx by Yas (Airtel's new brand)
    "65": "mixx",  # Mixx by Yas (ex-Tigo copper)
    "62": "halotel",  # Halotel (Viettel)
}


def detect_network(value):
    """Return the Snippe network id for a Tanzanian mobile number, or "unknown".

    Works with +255XXXXXXXXX, 255XXXXXXXXX, 0XXXXXXXXX or 7XXXXXXXXX shapes.
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        digits = f"255{digits[1:]}"
    elif len(digits) == 9 and digits.startswith(("6", "7")):
        digits = f"255{digits}"
    if len(digits) != 12:
        return "unknown"
    prefix = digits[3:5]
    return PREFIX_TO_NETWORK.get(prefix, "unknown")


def normalize_phone(value):
    """Best-effort Tanzanian mobile normalization to +255XXXXXXXXX. Returns an
    empty string when the number is unusable (never raises)."""
    if not value:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        digits = f"255{digits[1:]}"
    elif len(digits) == 9 and digits.startswith(("6", "7")):
        digits = f"255{digits}"
    elif len(digits) == 9 and digits.startswith("255"):
        digits = f"255{digits[3:]}"
    if len(digits) != 12 or not digits.startswith("255"):
        return ""
    return f"+{digits}"


def strip_plus(value):
    """The form Snippe documents as the canonical outbound format."""
    normalized = normalize_phone(value)
    return normalized[1:] if normalized else ""


def mask_phone(value):
    """2557******123 style mask for logs/receipts: never leak the full number."""
    normalized = normalize_phone(value)
    if not normalized:
        return value or ""
    return f"{normalized[:4]}******{normalized[-3:]}"


def int_amount(decimal_value):
    """Snippe takes amounts as integer smallest currency units (TZS has no
    subunits, so this is the raw shillings figure, rounded half-up)."""
    from decimal import ROUND_HALF_UP

    return int(decimal_value.quantize(1, rounding=ROUND_HALF_UP))