"""Email sent when a member is invited to join a group."""

import logging
import os

from django.conf import settings
from django.core.mail import send_mail

from .models import GroupInvitation

logger = logging.getLogger(__name__)


def send_group_invite_email(invitation: GroupInvitation) -> bool:
    frontend_url = os.environ.get(
        "FRONTEND_URL", "https://vikoba-theta.vercel.app"
    ).rstrip("/")
    accept_url = f"{frontend_url}/groups/invite/{invitation.token}"
    group_name = invitation.group.name
    inviter = (
        f"{invitation.invited_by.first_name} {invitation.invited_by.last_name}".strip()
        if invitation.invited_by_id
        else "A member"
    )

    subject = f"You've been invited to join {group_name} on {settings.SYSTEM_NAME}"
    html = f"""
<div style="margin:0;padding:0;background-color:#f3f4f6;font-family:Segoe UI,Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f3f4f6;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="width:560px;max-width:100%;background-color:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">
        <tr><td style="background-color:#1d4ed8;padding:22px 32px;">
          <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:0.5px;">{settings.SYSTEM_NAME}</span>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="margin:0 0 12px;font-size:20px;color:#0f172a;">You're invited to {group_name}</h1>
          <div style="font-size:15px;line-height:24px;color:#334155;">
            <p>{inviter} invited you to join the savings group <strong>{group_name}</strong>.</p>
            <p>Log in with the email you used to register, then tap the button below to accept:</p>
            <p style="margin:24px 0;">
              <a href="{accept_url}" style="display:inline-block;background-color:#1d4ed8;color:#ffffff;padding:12px 26px;border-radius:10px;text-decoration:none;font-weight:600;">Accept invitation</a>
            </p>
            <p style="font-size:13px;color:#64748b;">This invitation is valid for {invitation.TTL_DAYS} days. If the link does not work, open your group invitations inside the app.</p>
          </div>
        </td></tr>
        <tr><td style="padding:16px 32px;border-top:1px solid #eef2f7;font-size:12px;color:#64748b;line-height:18px;">
          You are receiving this email because an existing member invited you to their group on {settings.SYSTEM_NAME}.
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>
""".strip()

    text = (
        f"{inviter} invited you to join the savings group {group_name}.\n\n"
        f"Accept the invitation here: {accept_url}\n"
        f"Valid for {invitation.TTL_DAYS} days."
    )

    try:
        send_mail(
            subject,
            text,
            settings.DEFAULT_FROM_EMAIL,
            [invitation.email],
            fail_silently=False,
            html_message=html,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - never let mail break the invite
        logger.exception("Failed to send group invite to %s: %s", invitation.email, exc)
        return False