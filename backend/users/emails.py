"""Email helpers for user-facing verification emails (styled HTML + plain text)."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import EmailVerificationCode, PinSetupCode

logger = logging.getLogger(__name__)


def _wrap_html(title: str, body_html: str, footer_note: str = "") -> str:
    """Standard template used by all user emails (inline styles only)."""
    return f"""
<div style="margin:0;padding:0;background-color:#f3f4f6;font-family:Segoe UI,Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f3f4f6;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:560px;max-width:100%;background-color:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">
          <tr>
            <td style="background-color:#1d4ed8;padding:22px 32px;">
              <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:0.5px;">{settings.SYSTEM_NAME}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <h1 style="margin:0 0 12px;font-size:20px;color:#0f172a;">{title}</h1>
              <div style="font-size:15px;line-height:24px;color:#334155;">{body_html}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px;border-top:1px solid #eef2f7;font-size:12px;color:#64748b;line-height:18px;">
              You are receiving this email because you registered for {settings.SYSTEM_NAME}.
              If you didn't request this, you can safely ignore it.
              {footer_note}
            </td>
          </tr>
        </table>
        <p style="font-size:11px;color:#94a3b8;margin-top:12px;">&copy; {settings.SYSTEM_NAME}. All rights reserved.</p>
      </td>
    </tr>
  </table>
</div>
""".strip()


def _coupon_code_block(code: str, ttl_minutes: int, footer_line: str) -> str:
    """The prominent, dashed single-use code block shared by verification and
    PIN-setup emails."""
    return f"""
      <p style="margin:24px 0;">
        <span style="display:inline-block;background-color:#eff6ff;border:1px dashed #3b82f6;
                     border-radius:10px;padding:14px 28px;font-family:Consolas,Menlo,monospace;
                     font-size:28px;font-weight:700;letter-spacing:8px;color:#1d4ed8;">{code}</span>
      </p>
      <p>This code expires in <strong>{ttl_minutes} minutes</strong> and can only be used once.
         For your security, do not share it with anyone. {footer_line}</p>
"""


def _verification_body(code: str, ttl_minutes: int, email: str = "") -> str:
    import os, urllib.parse
    frontend = os.environ.get("FRONTEND_URL", "https://vikoba-theta.vercel.app").rstrip("/")
    qs = urllib.parse.urlencode({"email": email, "code": code}) if email else f"code={code}"
    return f"""
      <p>Hello,</p>
      <p>To keep your account secure we need to confirm your email address.
         Use the 6-digit code below or tap the button to confirm instantly:</p>
      {_coupon_code_block(code, ttl_minutes, "")}
      <p style="margin:20px 0;">
        <a href="{frontend}/verify-email?{qs}"
           style="display:inline-block;background-color:#115036;color:#ffffff;text-decoration:none;font-weight:700;padding:12px 24px;border-radius:10px;">Confirm email and go to login</a>
      </p>
      <p style="font-size:12px;color:#64748b;">Link expires in {ttl_minutes} minutes and can only be used once. If you didn't create an account, ignore this email.</p>
 """


def _pin_setup_body(code: str, ttl_minutes: int) -> str:
    return f"""
      <p>Hello,</p>
      <p>You asked to set up your <strong>4-digit secret PIN</strong>
         (\"namba za siri\") so you can log in faster with your phone number.</p>
      <p>Use the 6-digit code below to confirm it is really you:</p>
      {_coupon_code_block(code, ttl_minutes, "It is not the PIN itself, just the confirmation code.")}
"""


def _verification_plain(code: str, ttl_minutes: int) -> str:
    return (
        "Hello,\n\n"
        "To keep your account secure we need to confirm your email address.\n"
        f"Your 6-digit verification code is: {code}\n\n"
        f"This code expires in {ttl_minutes} minutes and can only be used once.\n"
        "For your security, do not share it with anyone."
    )


def _pin_setup_plain(code: str, ttl_minutes: int) -> str:
    return (
        "Hello,\n\n"
        "You asked to set up your 4-digit secret PIN so you can log in faster "
        "with your phone number.\n"
        f"Your confirmation code is: {code}\n\n"
        f"This code expires in {ttl_minutes} minutes and can only be used once. "
        "It is not the PIN itself - just the confirmation code.\n"
        "For your security, do not share it with anyone."
    )


def send_verification_email(code_obj: EmailVerificationCode) -> tuple[bool, str | None]:
    """Sends the styled 6-digit code.

    Returns ``(delivered: bool, error: str|None)``. A delivery failure never
    raises: the caller decides how to surface it (log + response metadata).
    """
    ttl = EmailVerificationCode.TTL_MINUTES
    subject = f"Your {settings.SYSTEM_NAME} verification code: {code_obj.code}"
    body_html = _wrap_html(
        "Verify your email address",
        _verification_body(code_obj.code, ttl, code_obj.user.email),
    )
    try:
        send_mail(
            subject,
            _verification_plain(code_obj.code, ttl),
            settings.DEFAULT_FROM_EMAIL,
            [code_obj.user.email],
            fail_silently=False,
            html_message=body_html,
        )
        return True, None
    except Exception as exc:  # noqa: BLE001 - never let mail break registration
        logger.exception("Failed to send verification email to %s: %s", code_obj.user.email, exc)
        return False, f"{type(exc).__name__}: {exc}"


def _deliver(subject: str, plain: str, html: str, recipient: str) -> tuple[bool, str | None]:
    """Shared delivery wrapper so every user email fails soft and reports why."""
    try:
        send_mail(
            subject,
            plain,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
            html_message=html,
        )
        return True, None
    except Exception as exc:  # noqa: BLE001 - never let mail break the request
        logger.exception("Failed to send email to %s: %s", recipient, exc)
        return False, f"{type(exc).__name__}: {exc}"


def send_pin_setup_code(code_obj: PinSetupCode) -> tuple[bool, str | None]:
    """Emails the PIN-setup confirmation code (styled HTML + plain text)."""
    ttl = PinSetupCode.TTL_MINUTES
    return _deliver(
        f"Your {settings.SYSTEM_NAME} PIN confirmation code: {code_obj.code}",
        _pin_setup_plain(code_obj.code, ttl),
        _wrap_html(
            "Set up your secret PIN",
            _pin_setup_body(code_obj.code, ttl),
            footer_note=(
                "Need help? Reply to this email and our team will assist you."
            ),
        ),
        code_obj.user.email,
    )


def send_password_reset_email(user, reset_url: str) -> tuple[bool, str | None]:
    """Emails a styled password-reset link. Returns (delivered, error)."""
    body_html = f"""
      <p>Hello {user.first_name or user.email},</p>
      <p>We received a request to reset your password. Tap the button below to
         choose a new one. The link is valid for a limited time.</p>
      <p style="margin:24px 0;">
        <a href="{reset_url}"
           style="display:inline-block;background-color:#1d4ed8;color:#ffffff;
                  text-decoration:none;font-weight:700;padding:12px 24px;
                  border-radius:10px;">Reset my password</a>
      </p>
      <p>If the button does not work, copy and open this link in your browser:</p>
      <p style="font-size:13px;word-break:break-all;color:#334155;">{reset_url}</p>
      <p>If you didn't request this, you can safely ignore this email.</p>
"""
    plain = (
        f"Hello {user.first_name or user.email},\n\n"
        "We received a request to reset your password.\n"
        f"Open this link to choose a new one: {reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    return _deliver(
        f"Reset your {settings.SYSTEM_NAME} password",
        plain,
        _wrap_html("Reset your password", body_html),
        user.email,
    )