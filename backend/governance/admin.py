from django.contrib import admin

from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStep,
    GroupWithdrawalPolicy,
)


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0


class ApprovalActionInline(admin.TabularInline):
    model = ApprovalAction
    extra = 0
    readonly_fields = [
        "actor",
        "actor_type",
        "action",
        "decision",
        "reason",
        "from_status",
        "to_status",
        "ip_address",
        "created_at",
    ]


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "request_type",
        "group",
        "requester",
        "amount",
        "currency",
        "status",
        "decision",
        "created_at",
    ]
    list_filter = ["request_type", "status", "decision", "group"]
    search_fields = ["resource_description", "requester__email", "amount"]
    readonly_fields = [
        "content_type",
        "object_id",
        "created_at",
        "updated_at",
    ]
    inlines = [ApprovalStepInline, ApprovalActionInline]


@admin.register(GroupWithdrawalPolicy)
class GroupWithdrawalPolicyAdmin(admin.ModelAdmin):
    list_display = [
        "group",
        "auto_approve_limit",
        "max_withdrawal_limit",
        "reviewer_role",
        "review_levels",
        "updated_at",
    ]
    readonly_fields = ["updated_by", "updated_at"]