from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import (
    DepositRequest,
    MembershipPlan,
    SavingsAccount,
    SavingsProduct,
    SavingsTransaction,
    WithdrawalRequest,
)
from members.models import Member


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsProduct
        fields = (
            "id",
            "name",
            "code",
            "minimum_balance",
            "interest_rate",
            "withdrawal_fee",
            "allows_withdrawals",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")



class AccountSerializer(WritableNestedModelSerializer):
    product = serializers.SlugRelatedField(slug_field='name', queryset=SavingsProduct.objects.all())
    member = serializers.SlugRelatedField(slug_field='membership_number', queryset=Member.objects.all())
    
    
    class Meta:
        model = SavingsAccount
        exclude = ("opened_at",)
        extra_kwargs = {
            'account_number': {
                'validators': [
                    UniqueValidator(
                        queryset=SavingsAccount.objects.all(),
                        message="An account with this account number already exists."
                    )
                ]
            }
        }


class MyAccountSerializer(serializers.ModelSerializer):
    """Read-only summary of a member's own savings account (self-service)."""
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = SavingsAccount
        fields = ["id", "account_number", "product", "product_name", "product_code", "balance", "is_active", "opened_at"]


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for reading transaction details"""
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    member = serializers.CharField(source='account.member.membership_number', read_only=True)
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = SavingsTransaction
        fields = [
            'id',
            'account',
            'account_number',
            'member',
            'transaction_type',
            'amount',
            'reference',
            'narration',
            'performed_by',
            'performed_by_username',
            'created_at'
        ]
        read_only_fields = ['id', 'reference', 'created_at']


class TransactionCreateSerializer(serializers.Serializer):
    """Serializer for creating transactions via the API"""
    account_number = serializers.CharField(max_length=20)
    transaction_type = serializers.ChoiceField(choices=SavingsTransaction.TRANSACTION_TYPES)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    narration = serializers.CharField(required=False, allow_blank=True, default="")
    
    def validate_amount(self, value):
        """Ensure amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value
    
    def validate_account_number(self, value):
        """Ensure account exists"""
        try:
            account = SavingsAccount.objects.get(account_number=value)
            if not account.is_active:
                raise serializers.ValidationError("Account is not active")
        except SavingsAccount.DoesNotExist:
            raise serializers.ValidationError("Account does not exist")
        return value


class MemberTransactionSerializer(serializers.ModelSerializer):
    """A member's own savings statement line."""
    account_number = serializers.CharField(source="account.account_number", read_only=True)

    class Meta:
        model = SavingsTransaction
        fields = [
            "id",
            "account",
            "account_number",
            "transaction_type",
            "amount",
            "reference",
            "narration",
            "created_at",
        ]
        read_only_fields = fields


class DepositRequestSerializer(serializers.ModelSerializer):
    """Member view of a deposit request."""
    account_number = serializers.CharField(source="account.account_number", read_only=True)
    product_name = serializers.CharField(source="account.product.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DepositRequest
        fields = [
            "id",
            "account",
            "account_number",
            "product_name",
            "amount",
            "channel",
            "transaction_code",
            "reference",
            "status",
            "status_display",
            "requested_at",
            "processed_at",
            "decline_reason",
        ]
        read_only_fields = ["id", "reference", "status", "requested_at", "processed_at", "decline_reason"]


class DepositRequestCreateSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(max_length=20)

    class Meta:
        model = DepositRequest
        fields = ["account_number", "amount", "channel", "transaction_code"]

    def validate_account_number(self, value):
        try:
            account = SavingsAccount.objects.select_related("member").get(account_number=value)
        except SavingsAccount.DoesNotExist as exc:
            raise serializers.ValidationError("Account does not exist.") from exc
        if not account.is_active:
            raise serializers.ValidationError("Account is not active.")
        member = self.context["request"].user.member
        if account.member_id != member.pk:
            raise serializers.ValidationError("You can only deposit into your own account.")
        self.context["account"] = account
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    """Member view of a withdrawal request."""
    account_number = serializers.CharField(source="account.account_number", read_only=True)
    product_name = serializers.CharField(source="account.product.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            "id",
            "account",
            "account_number",
            "product_name",
            "amount",
            "narration",
            "reference",
            "status",
            "status_display",
            "requested_at",
            "processed_at",
            "decline_reason",
        ]
        read_only_fields = ["id", "reference", "status", "requested_at", "processed_at", "decline_reason"]


class WithdrawalRequestCreateSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(max_length=20)

    class Meta:
        model = WithdrawalRequest
        fields = ["account_number", "amount", "narration"]

    def validate_account_number(self, value):
        try:
            account = SavingsAccount.objects.select_related("member").get(account_number=value)
        except SavingsAccount.DoesNotExist as exc:
            raise serializers.ValidationError("Account does not exist.") from exc
        if not account.is_active:
            raise serializers.ValidationError("Account is not active.")
        member = self.context["request"].user.member
        if account.member_id != member.pk:
            raise serializers.ValidationError("You can only withdraw from your own account.")
        self.context["account"] = account
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class DepositRequestDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    decline_reason = serializers.CharField(required=False, allow_blank=True, default="")


class WithdrawalRequestDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    decline_reason = serializers.CharField(required=False, allow_blank=True, default="")


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = ["id", "name", "price", "currency", "interval", "features", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
