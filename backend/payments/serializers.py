from rest_framework import serializers

from accounts.models import MemberSubscription, MembershipPlan
from .models import PaymentTransaction, ReconciliationRecord, WebhookEvent


class PaymentTransactionSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="internal_reference", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    subscription = serializers.IntegerField(source="subscription_id", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "reference",
            "transaction_type",
            "amount",
            "currency",
            "status",
            "provider",
            "provider_reference",
            "internal_reference",
            "phone",
            "metadata",
            "fee",
            "net_amount",
            "subscription",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields


class WebhookPayloadSerializer(serializers.Serializer):
    """Validates the top-level Snippe webhook envelope."""

    id = serializers.CharField()
    type = serializers.CharField()
    api_version = serializers.CharField(required=False, default="")
    data = serializers.JSONField(default=dict)
    created_at = serializers.CharField(required=False, allow_blank=True)


class ReconciliationRecordSerializer(serializers.ModelSerializer):
    internal_reference_display = serializers.CharField(source="internal_reference", read_only=True)
    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = ReconciliationRecord
        fields = [
            "id",
            "payment",
            "internal_reference_display",
            "provider",
            "provider_reference",
            "event_id",
            "issue_type",
            "expected_amount",
            "actual_amount",
            "expected_currency",
            "actual_currency",
            "expected_status",
            "actual_status",
            "resolution_status",
            "notes",
            "resolved_by",
            "resolved_by_name",
            "resolved_at",
            "resolution_note",
            "created_at",
        ]
        read_only_fields = fields


class PayWithdrawalSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = ["id", "name", "price", "currency", "interval"]


class MemberSubscriptionSerializer(serializers.ModelSerializer):
    """Member-facing view of one subscription with its plan and payment link."""

    plan = SubscriptionPlanSerializer(read_only=True)
    payment_reference = serializers.SerializerMethodField()

    class Meta:
        model = MemberSubscription
        fields = [
            "id",
            "status",
            "plan",
            "payment_reference",
            "started_at",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_payment_reference(self, obj):
        tx = obj.payment_transactions.order_by("-created_at").first()
        return tx.internal_reference if tx else None