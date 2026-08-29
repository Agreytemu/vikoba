from django.contrib import admin

from .models import (
    GroupContribution,
    GroupInvitation,
    GroupMembership,
    GroupShare,
    VikobaGroup,
)


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


class GroupInvitationInline(admin.TabularInline):
    model = GroupInvitation
    extra = 0


class VikobaGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "area", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "area")
    inlines = [GroupMembershipInline, GroupInvitationInline]


class GroupContributionAdmin(admin.ModelAdmin):
    list_display = ("group", "member", "amount", "month", "status", "created_at")
    list_filter = ("status", "month")
    search_fields = ("group__name", "member__first_name", "member__last_name")


class GroupShareAdmin(admin.ModelAdmin):
    list_display = ("group", "member", "quantity", "amount_paid", "created_at")


admin.site.register(VikobaGroup, VikobaGroupAdmin)
admin.site.register(GroupContribution, GroupContributionAdmin)
admin.site.register(GroupShare, GroupShareAdmin)