"""Domain helpers for email verification codes and quick-login PINs."""

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.utils import timezone

from .emails import send_pin_setup_code, send_verification_email
from .models import EmailVerificationCode, PinSetupCode
from .models import User as AuthUser


def _new_digit_code(previous: str | None = None, length: int = 6) -> str:
    """Zero-padded random digit code (e.g. '042913'), never equal to the
    previous code so a re-send is always visibly different."""
    code = f"{secrets.randbelow(10 ** length):0{length}d}"
    if previous is not None:
        guard = 0
        while code == previous and guard < 10:
            code = f"{secrets.randbelow(10 ** length):0{length}d}"
            guard += 1
    return code


def issue_email_code(user) -> EmailVerificationCode:
    """Rotates any outstanding code and issues a fresh expiring 6-digit code.

    Delivery results (email_sent/email_error) are attached as attributes on the
    returned object so API responses can tell the client whether the email went
    out (or why not) instead of leaving the user waiting indefinitely.
    """
    user.email_verification_codes.filter(is_used=False).update(is_used=True)

    previous = user.email_verification_codes.order_by("-created_at", "-pk").first()
    code = _new_digit_code(previous.code if previous else None, 6)
    obj = EmailVerificationCode.objects.create(
        user=user,
        code=code,
        expires_at=timezone.now()
        + timedelta(minutes=EmailVerificationCode.TTL_MINUTES),
    )
    sent, error = send_verification_email(obj)
    obj.email_sent = sent
    obj.email_error = error
    return obj


def verify_email_code(user, code: str) -> bool:
    """Validates the code (rotation, expiry, attempts). Returns success."""
    code_obj = (
        user.email_verification_codes.filter(is_used=False).order_by("-created_at", "-pk").first()
    )
    if code_obj is None or code_obj.is_expired:
        return False

    normalized = "".join(ch for ch in str(code).strip() if ch.isdigit())
    if normalized != code_obj.code:
        code_obj.attempts += 1
        if code_obj.attempts >= EmailVerificationCode.MAX_ATTEMPTS:
            code_obj.is_used = True
        code_obj.save(update_fields=["attempts", "is_used"])
        return False

    code_obj.is_used = True
    code_obj.save(update_fields=["is_used"])
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return True


def issue_pin_setup_code(user) -> PinSetupCode:
    """Rotate any outstanding PIN-setup code and email a fresh one.

    Delivery results (email_sent/email_error) are attached so API responses can
    tell the client whether the email went out (or why not).
    """
    user.pin_setup_codes.filter(is_used=False).update(is_used=True)

    previous = user.pin_setup_codes.order_by("-created_at", "-pk").first()
    code = _new_digit_code(previous.code if previous else None, 6)
    obj = PinSetupCode.objects.create(
        user=user,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=PinSetupCode.TTL_MINUTES),
    )
    sent, error = send_pin_setup_code(obj)
    obj.email_sent = sent
    obj.email_error = error
    return obj


def verify_pin_setup_code(user, code: str) -> bool:
    """Validates the PIN-setup confirmation code. Returns success."""
    code_obj = (
        user.pin_setup_codes.filter(is_used=False).order_by("-created_at", "-pk").first()
    )
    if code_obj is None or code_obj.is_expired:
        return False

    normalized = "".join(ch for ch in str(code).strip() if ch.isdigit())
    if normalized != code_obj.code:
        code_obj.attempts += 1
        if code_obj.attempts >= PinSetupCode.MAX_ATTEMPTS:
            code_obj.is_used = True
        code_obj.save(update_fields=["attempts", "is_used"])
        return False

    code_obj.is_used = True
    code_obj.save(update_fields=["is_used"])
    return True


def user_by_phone(phone_number: str):
    """Find a member login account by its phone number (format agnostic).

    Accepts +2547…, 07…, 2547…, 7… and returns ``None`` when no member account
    exists for the number — the caller decides how much to disclose.
    """
    from members.models import Member
    from .models import User

    digits = "".join(ch for ch in phone_number if ch.isdigit())
    if not digits:
        return None
    tail = digits[-9:]
    if not tail:
        return None

    candidates = [f"+254{tail}", f"254{tail}", f"0{tail}", tail, f"+{tail}"]
    member = Member.objects.filter(phone_number__in=candidates).first()
    if member is not None and member.user is not None:
        return member.user

    # Fallback: compare trailing digits across all members (small scale).
    for m in Member.objects.filter(user__isnull=False).select_related("user"):
        mdigits = "".join(ch for ch in m.phone_number if ch.isdigit())
        if mdigits and mdigits.endswith(tail):
            return m.user
    return None


def verify_pin(user, pin: str) -> tuple[str, int]:
    """Check a quick-login PIN with lockout protection.

    Returns ``(status, seconds)`` where status is one of:
      - ``"ok"``      PIN correct (attempt counter reset)
      - ``"invalid"`` wrong PIN, still allowed
      - ``"locked"``  PIN locked; ``seconds`` is until it unlocks
    """
    if user.is_pin_locked:
        remain = int((user.pin_locked_until - timezone.now()).total_seconds())
        return "locked", max(remain, 1)

    if check_password(pin, user.pin_hash or ""):
        if user.pin_attempts:
            user.pin_attempts = 0
            user.save(update_fields=["pin_attempts"])
        return "ok", 0

    user.pin_attempts += 1
    locked = user.pin_attempts >= user.__class__.PIN_MAX_ATTEMPTS
    fields = ["pin_attempts"]
    if locked:
        user.pin_locked_until = timezone.now() + timedelta(minutes=AuthUser.PIN_LOCK_MINUTES)
        fields.append("pin_locked_until")
    user.save(update_fields=fields)
    if locked:
        return "locked", AuthUser.PIN_LOCK_MINUTES * 60
    return "invalid", 0


def is_valid_pin(pin: str) -> bool:
    """A quick-login PIN is exactly 4 digits."""
    return len(pin) == 4 and pin.isdigit()