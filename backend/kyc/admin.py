"""Django admin for the KYC domain.

The KYC model is intentionally read-mostly here: a KYC status change is a
security-relevant action that must go through the audited service layer
(``kyc.services.SubmitVerificationService`` / manual review endpoints). The
admin can inspect profiles, requests and the append-only event log, but can
never flip ``status`` by hand without an audit event being recorded.
"""
from django.contrib import admin

from .models import KYCEvent, KYCProfile, KYCVerificationRequest


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "status",
        "verification_level",
        "verification_method",
        "provider",
        "verified_at",
        "expires_at",
    )
    list_filter = ("status", "verification_level", "verification_method", "provider")
    search_fields = ("member__membership_number", "member__user__email", "member__full_name")
    readonly_fields = (
        "member",
        "status",
        "verification_level",
        "verification_method",
        "provider",
        "provider_reference",
        "failure_code",
        "failure_reason",
        "verified_at",
        "expires_at",
        "last_checked_at",
    )
    fieldsets = (
        (None, {"fields": ("member", "status", "verification_level")}),
        ("Verification", {"fields": ("verification_method", "provider", "provider_reference")}),
        ("Outcome", {"fields": ("failure_code", "failure_reason", "verified_at", "expires_at")}),
        ("Health", {"fields": ("last_checked_at",)}),
    )


@admin.register(KYCVerificationRequest)
class KYCVerificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_ref",
        "profile",
        "status",
        "attempt_count",
        "provider",
        "verification_status",
        "submitted_at",
        "completed_at",
    )
    list_filter = ("status", "verification_status", "provider")
    search_fields = ("request_ref", "profile__member__membership_number")
    readonly_fields = (
        "profile",
        "request_ref",
        "idempotency_key",
        "status",
        "attempt_count",
        "max_attempts",
        "provider",
        "provider_reference",
        "verification_status",
        "failure_code",
        "failure_reason",
        "match_result",
        "verified_name",
        "verified_dob",
        "submitted_at",
        "completed_at",
    )


@admin.register(KYCEvent)
class KYCEventAdmin(admin.ModelAdmin):
    """Append-only log — no add/change/delete in admin."""

    list_display = ("profile", "action", "actor_type", "actor", "ip_address", "created_at")
    list_filter = ("action", "actor_type")
    search_fields = ("profile__member__membership_number", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False