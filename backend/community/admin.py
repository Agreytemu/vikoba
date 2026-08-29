from django.contrib import admin

from .models import Announcement, Meeting


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "pinned", "author", "created_at")
    list_filter = ("status", "pinned")
    search_fields = ("title", "body")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "location", "created_by")
    search_fields = ("title", "description")