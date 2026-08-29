from rest_framework import serializers

from .models import WhatsAppSession


class WhatsAppSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    can_manage = serializers.BooleanField(read_only=True, default=False)
    owner_email = serializers.CharField(source="owner.email", read_only=True, default="")

    class Meta:
        model = WhatsAppSession
        fields = [
            "id",
            "session_id",
            "owner_type",
            "group",
            "group_name",
            "display_name",
            "status",
            "status_display",
            "phone",
            "is_primary",
            "last_error",
            "can_manage",
            "owner_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WhatsAppSessionCreateSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = WhatsAppSession
        fields = ["session_id", "owner_type", "group", "display_name", "group_name"]
        read_only_fields = ["session_id", "group_name"]


class WhatsAppTestSendSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=20)
    text = serializers.CharField(max_length=4000)


class WhatsAppSessionPairSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class WhatsAppBulkSendSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4000)
    group_id = serializers.IntegerField(required=False)
    phones = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if not (attrs.get("group_id") or attrs.get("phones")):
            raise serializers.ValidationError(
                "Provide either a group_id or a phones list."
            )
        return attrs