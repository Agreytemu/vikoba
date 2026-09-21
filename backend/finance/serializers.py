"""DRF serializers for the finance API."""
from decimal import Decimal

from rest_framework import serializers

from .models import AuditEvent, FinancialAccount, FinancialTransaction, JournalEntry


class FinancialAccountSerializer(serializers.ModelSerializer):
    account_type_label = serializers.CharField(source="get_account_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    balance = serializers.SerializerMethodField()

    class Meta:
        model = FinancialAccount
        fields = (
            "id",
            "account_number",
            "name",
            "account_type",
            "account_type_label",
            "currency",
            "status",
            "status_label",
            "member",
            "group",
            "balance",
            "created_at",
        )
        read_only_fields = ("id", "account_number", "created_at")

    def get_balance(self, obj):
        from finance.services.balances import account_balance

        return str(account_balance(obj))


class JournalEntrySerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source="account.account_number", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalEntry
        fields = ("id", "account_number", "account_name", "entry_type", "amount", "currency", "description", "position")


class FinancialTransactionSerializer(serializers.ModelSerializer):
    entries = JournalEntrySerializer(many=True, read_only=True)
    transaction_type_label = serializers.CharField(source="get_transaction_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reversal_of_reference = serializers.CharField(source="reversal_of.reference", read_only=True)
    reversals = serializers.SerializerMethodField()
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    member_name = serializers.SerializerMethodField()
    initiated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FinancialTransaction
        fields = (
            "id",
            "reference",
            "transaction_type",
            "transaction_type_label",
            "status",
            "status_label",
            "amount",
            "currency",
            "description",
            "external_reference",
            "provider",
            "provider_transaction_id",
            "group",
            "group_name",
            "member",
            "member_name",
            "initiated_by",
            "initiated_by_name",
            "savings_transaction",
            "payment_transaction",
            "deposit_request",
            "withdrawal_request",
            "contribution",
            "reversal_of",
            "reversal_of_reference",
            "reversals",
            "reversal_reason",
            "posted_at",
            "created_at",
            "updated_at",
            "entries",
        )
        read_only_fields = fields

    def get_reversals(self, obj):
        return list(obj.reversals.values_list("reference", flat=True))

    def get_member_name(self, obj):
        member = obj.member
        if member is None:
            return ""
        return f"{member.first_name} {member.last_name}".strip()

    def get_initiated_by_name(self, obj):
        user = obj.initiated_by
        if user is None:
            return ""
        return user.get_full_name() or user.username


class ReversalRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False, trim_whitespace=True)


class JournalRequestSerializer(serializers.Serializer):
    """Staff-only manual journal (adjustment / group expense / transfer / refund)."""

    transaction_type = serializers.ChoiceField(choices=FinancialTransaction.TransactionType.choices)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(choices=["TZS"], default="TZS")
    description = serializers.CharField(max_length=255, allow_blank=True, required=False)
    entries = serializers.ListField(min_length=2, max_length=64, child=serializers.JSONField())
    idempotency_key = serializers.CharField(max_length=120, required=False, allow_blank=True, trim_whitespace=True)

    def validate_entries(self, value):
        if not all(isinstance(e, dict) and {"account", "entry_type", "amount"} <= set(e) for e in value):
            raise serializers.ValidationError("Each entry needs account, entry_type and amount.")
        return value


class AuditEventSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = AuditEvent
        fields = ("id", "user", "user_email", "action", "reference", "transaction", "metadata", "ip_address", "created_at")
        read_only_fields = fields