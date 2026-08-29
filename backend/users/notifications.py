from .models import Notification
from .sms import send_sms


def notify_user(user, title, body="", *, kind="info", link="", sms_to=None):
    """Create an in-app notification (optionally also deliver an SMS)."""
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=kind,
        link=link,
    )
    if sms_to:
        send_sms(sms_to, f"{title} - {body}".strip(" -"))
    return notification