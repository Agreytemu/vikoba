from django.contrib import admin
from django.utils.html import format_html

from .models import PaymentTransaction, ReconciliationRecord, WebhookEvent


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "internal_reference",
        "member",
        "transaction_type",
        "amount",
        "currency",
        "status",
        "provider_reference",
        "created_at",
    )
    list_filter = ("transaction_type", "status", "currency", "provider")
    search_fields = ("internal_reference", "provider_reference", "member__membership_number")
    readonly_fields = (
        "internal_reference",
        "idempotency_key",
        "provider_reference",
        "created_at",
        "updated_at",
        "completed_at",
    )
    date_hierarchy = "created_at"
    fieldsets = (
        (None, {"fields": ("internal_reference", "idempotency_key", "status", "transaction_type")}),
        ("Business object", {"fields": ("member", "group", "contribution", "loan", "withdrawal")}),
        ("Money", {"fields": ("amount", "currency", "fee", "net_amount")}),
        ("Provider", {"fields": ("provider", "provider_reference", "external_reference", "phone")}),
        ("Metadata", {"fields": ("metadata", "failure_reason")}),
        ("Dates", {"fields": ("created_at", "updated_at", "completed_at")}),
    )

    def colored_status(self, obj):
        color = {"SUCCESS": "#1a7f37", "FAILED": "#cf222e"}.get(obj.status, "#24292f")
        return format_html(f'<span style="color:{color};font-weight:600">{obj.status}</span>')

    colored_status.short_description = "Status"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "processed", "received_at")
    list_filter = ("event_type", "processed")
    search_fields = ("event_id",)
    readonly_fields = ("event_id", "event_type", "payload", "received_at")
    date_hierarchy = "received_at"


@admin.register(ReconciliationRecord)
class ReconciliationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "issue_type",
        "provider_reference",
        "internal_reference",
        "payment",
        "resolution_status",
        "created_at",
    )
    list_filter = ("issue_type", "resolution_status", "provider")
    search_fields = (
        "provider_reference",
        "internal_reference",
        "payment__internal_reference",
        "notes",
    )
    readonly_fields = (
        "payment",
        "provider",
        "provider_reference",
        "internal_reference",
        "event_id",
        "issue_type",
        "created_at",
    )
    date_hierarchy = "created_at"
    fieldsets = (
        ("Exception", {"fields": ("issue_type", "resolution_status", "payment", "event_id")}),
        ("References", {"fields": ("provider", "provider_reference", "internal_reference")}),
        ("Facts", {"fields": ("expected_amount", "actual_amount", "expected_currency", "actual_currency")}),
        ("Status", {"fields": ("expected_status", "actual_status", "notes")}),
        ("Resolution audit", {"fields": ("resolved_by", "resolved_at", "resolution_note")}),
    )