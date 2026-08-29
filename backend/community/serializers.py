from rest_framework import serializers

from .models import Announcement, Meeting


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "status",
            "status_display",
            "pinned",
            "author",
            "author_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "author_name", "created_at", "updated_at"]


class MeetingSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "starts_at",
            "ends_at",
            "location",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["created_by", "created_by_name", "created_at"]