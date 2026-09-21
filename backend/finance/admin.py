from django.contrib import admin

from .models import AuditEvent, FinancialAccount, FinancialTransaction, JournalEntry, ReferenceCounter


@admin.register(ReferenceCounter)
class ReferenceCounterAdmin(admin.ModelAdmin):
    """Sequence counters are read-only to keep references immutable."""

    list_display = ("prefix", "day", "last_sequence")
    readonly_fields = ("prefix", "day", "last_sequence")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class JournalEntryInline(admin.TabularInline):
    model = JournalEntry
    extra = 0
    can_delete = False
    readonly_fields = ("account", "entry_type", "amount", "currency", "description", "position")


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = (
        "account_number",
        "name",
        "account_type",
        "currency",
        "member",
        "group",
        "status",
        "created_at",
    )
    list_filter = ("account_type", "currency", "status")
    search_fields = ("account_number", "name")


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "transaction_type",
        "status",
        "amount",
        "currency",
        "group",
        "member",
        "posted_at",
        "created_at",
    )
    list_filter = ("transaction_type", "status", "currency", "created_at")
    search_fields = ("reference", "provider_transaction_id", "idempotency_key")
    date_hierarchy = "created_at"
    readonly_fields = (
        "reference",
        "idempotency_key",
        "reversal_of",
        "reversal_reason",
        "posted_at",
    )
    inlines = (JournalEntryInline,)
    autocomplete_fields = ("member",)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "account", "entry_type", "amount", "currency", "position")
    list_filter = ("entry_type", "currency")
    search_fields = ("transaction__reference", "account__account_number")
    readonly_fields = ("transaction", "account", "entry_type", "amount", "currency", "description", "position")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "reference", "transaction", "ip_address")
    list_filter = ("action", "created_at")
    search_fields = ("reference", "user__email")
    readonly_fields = ("user", "action", "reference", "transaction", "metadata", "ip_address", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False