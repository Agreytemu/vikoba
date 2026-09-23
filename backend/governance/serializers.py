"""API serializers for the governance app."""
from decimal import Decimal

from rest_framework import serializers

from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStep,
    GroupWithdrawalPolicy,
)
from governance.policy import effective_values, get_or_create_policy


class ApprovalStepSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalStep
        fields = ["level", "role", "status", "approved_by", "approved_by_name", "approved_at", "reason"]

    def get_approved_by_name(self, obj):
        if obj.approved_by is None:
            return ""
        name = getattr(obj.approved_by, "get_full_name", None)
        return name() if name else str(obj.approved_by)


class ApprovalActionSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalAction
        fields = ["action", "actor_type", "actor_name", "decision", "reason", "from_status", "to_status", "ip_address", "created_at"]

    def get_actor_name(self, obj):
        if obj.actor is None:
            return "System" if obj.actor_type == ApprovalAction.ACTOR_SYSTEM else ""
        return f"{obj.actor.get_full_name() or obj.actor.email}"


class WithdrawalContextSerializer(serializers.Serializer):
    """Flattened, read-only view of the WithdrawalRequest backing a request."""

    reference = serializers.CharField()
    member_name = serializers.SerializerMethodField()
    account_number = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    status = serializers.CharField()
    decline_reason = serializers.CharField()
    requested_at = serializers.DateTimeField()
    network = serializers.SerializerMethodField()

    def get_member_name(self, obj):
        member = getattr(obj, "member", None)
        if member is None:
            return ""
        return f"{member.first_name or ''} {member.last_name or ''}".strip()

    def get_account_number(self, obj):
        account = getattr(obj, "account", None)
        return account.account_number if account else ""

    def get_balance(self, obj):
        account = getattr(obj, "account", None)
        return str(account.balance) if account else "0"

    def get_network(self, obj):
        from governance.withdrawals import request_for

        approval = request_for(obj)
        if approval is None:
            return ""
        return approval.metadata.get("network", "")


class ApprovalRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    requester_id = serializers.IntegerField(source="requester.pk", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, allow_null=True)
    steps = ApprovalStepSerializer(many=True, read_only=True)
    withdrawal = serializers.SerializerMethodField()
    can_act = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    is_requester = serializers.SerializerMethodField()
    decision_label = serializers.CharField(source="get_decision_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "request_type",
            "resource_description",
            "requester_id",
            "requester_name",
            "group",
            "group_name",
            "amount",
            "currency",
            "required_level",
            "required_role",
            "status",
            "status_label",
            "decision",
            "decision_label",
            "decision_reason",
            "rules_passed",
            "policy_version",
            "steps",
            "metadata",
            "expires_at",
            "created_at",
            "updated_at",
            "withdrawal",
            "can_act",
            "can_cancel",
            "is_requester",
        ]
        read_only_fields = fields

    def get_requester_name(self, obj):
        if obj.requester is None:
            return ""
        return obj.requester.get_full_name() or obj.requester.email

    def get_withdrawal(self, obj):
        if obj.request_type != "WITHDRAWAL" or obj.object_id is None:
            return None
        resource = obj.resource
        if resource is None:
            return None
        return WithdrawalContextSerializer(resource).data

    def get_can_act(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        from governance import workflow

        return obj.status == "PENDING" and obj.requester_id != request.user.pk and workflow.can_review(request.user, obj)

    def get_can_cancel(self, obj):
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        from governance import workflow

        return obj.status == "PENDING" and (
            obj.requester_id == request.user.pk
            or request.user.is_superuser
            or (getattr(request.user, "role", None) in workflow.SYSTEM_OFFICER_ROLES)
            or workflow.can_review(request.user, obj)
        )

    def get_is_requester(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.requester_id == request.user.pk)


class ApprovalDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "cancel"])
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class GroupWithdrawalPolicySerializer(serializers.ModelSerializer):
    """Read/write view of a group's withdrawal policy (committee + staff only)."""

    effective = serializers.SerializerMethodField()

    class Meta:
        model = GroupWithdrawalPolicy
        fields = [
            "group",
            "auto_approve_limit",
            "max_withdrawal_limit",
            "min_withdrawal_amount",
            "weekly_withdrawal_limit",
            "weekly_withdrawal_count",
            "monthly_withdrawal_limit",
            "min_retained_ratio",
            "review_on_outstanding_loan",
            "review_on_outstanding_penalty",
            "kyc_level_required",
            "review_levels",
            "reviewer_role",
            "updated_by",
            "updated_at",
            "effective",
        ]
        read_only_fields = ["group", "updated_by", "updated_at", "effective"]

    def get_effective(self, obj):
        values = effective_values(obj)
        return {
            "auto_approve_limit": str(values["auto_approve_limit"] or ""),
            "max_withdrawal_limit": str(values["max_withdrawal_limit"] or ""),
            "min_withdrawal_amount": str(values["min_withdrawal_amount"] or ""),
            "min_retained_ratio": str(values["min_retained_ratio"]),
            "review_levels": values["review_levels"],
            "reviewer_role": values["reviewer_role"],
            "kyc_level_required": values["kyc_level_required"],
            "policy_version": values["policy_version"],
        }

    def validate_auto_approve_limit(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Must be positive or leave empty.")
        return value

    def validate_max_withdrawal_limit(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Must be positive or leave empty.")
        return value

    def validate_min_retained_ratio(self, value):
        if value is not None and not (Decimal("0") <= value <= Decimal("1")):
            raise serializers.ValidationError("Must be between 0 and 1.")
        return value


def policy_payload(group) -> dict:
    return GroupWithdrawalPolicySerializer(get_or_create_policy(group)).data