from django.contrib import admin

from .models import WhatsAppSession


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_id",
        "owner_type",
        "group",
        "display_name",
        "status",
        "phone",
        "is_primary",
        "updated_at",
    )
    list_filter = ("owner_type", "status", "is_primary")
    search_fields = ("session_id", "display_name", "phone")
    readonly_fields = ("created_at", "updated_at")