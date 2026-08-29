from django.conf import settings
from django.db import models


class WhatsAppSession(models.Model):
    """A paired WhatsApp device owned by the system admin or a group chairperson.

    Credentials themselves live in Supabase via the Baileys gateway (sessions
    are paired by phone pairing code — no QR, auth stored on Supabase). Django
    only stores the reference, who owns it, and the last known status.
    """

    class OwnerType(models.TextChoices):
        ADMIN = "ADMIN", "System admin"
        CHAIR = "CHAIR", "Group chairperson"

    STATUS_CONNECTED = "connected"
    STATUS_CHOICES = (
        ("connecting", "Connecting"),
        ("awaiting_pairing", "Awaiting pairing code"),
        (STATUS_CONNECTED, "Connected"),
        ("disconnected", "Disconnected"),
        ("logged_out", "Logged out"),
        ("error", "Error"),
    )

    session_id = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="whatsapp_owned",
        help_text="User account the device is saved to (the chairperson or the staff member).",
    )
    owner_type = models.CharField(max_length=8, choices=OwnerType.choices)
    group = models.ForeignKey(
        "groups.VikobaGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="whatsapp_sessions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="whatsapp_sessions_created",
    )
    display_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="connecting"
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    is_primary = models.BooleanField(
        default=False,
        help_text="Preferred sender for that owner scope (e.g. the admin's main device).",
    )
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "-updated_at"]
        indexes = [models.Index(fields=["owner_type", "status"])]

    def __str__(self):
        return self.display_name or self.session_id

    def refresh_from_bridge(self, bridge_status):
        """Sync a bridge status payload into this row (never stores the code)."""
        self.status = bridge_status.get("status", self.status)
        if bridge_status.get("phone"):
            self.phone = bridge_status["phone"].lstrip("+")
        self.save(update_fields=["status", "phone", "updated_at"])