from decimal import Decimal

from rest_framework import serializers
from django.db.models import Sum

from members.models import Member
from .models import (
    ElectedRole,
    GroupActivity,
    GroupContribution,
    GroupInvitation,
    GroupMembership,
    GroupRoleCandidate,
    GroupRoleVote,
    GroupShare,
    MemberShareOut,
    ShareOut,
    VikobaGroup,
)


class MemberBriefSerializer(serializers.ModelSerializer):
    """Lightweight member summary shown inside group views."""

    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            "membership_number",
            "first_name",
            "last_name",
            "profile_image",
        ]

    def get_profile_image(self, obj):
        user = getattr(obj, "user", None)
        if user is None:
            return None
        return user.profile_image.name if user.profile_image else None


class GroupMembershipSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    is_verified = serializers.BooleanField(source="member.is_verified", read_only=True)
    member_status = serializers.CharField(source="member.status", read_only=True)
    contribution_total = serializers.SerializerMethodField()
    pending_contribution_total = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = [
            "id",
            "member",
            "role",
            "shares_count",
            "joined_at",
            "is_active",
            "is_verified",
            "member_status",
            "contribution_total",
            "pending_contribution_total",
        ]

    def _sum_for(self, obj, status):
        total = obj.member.group_contributions.filter(
            group=obj.group,
            status=status,
        ).aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0")

    def get_contribution_total(self, obj):
        return self._sum_for(obj, GroupContribution.Status.CONFIRMED)

    def get_pending_contribution_total(self, obj):
        return self._sum_for(obj, GroupContribution.Status.PENDING)


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VikobaGroup
        fields = ["name", "area", "region", "country", "description"]

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Group name is required.")
        return value.strip()


class GroupListSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    my_shares = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = VikobaGroup
        fields = [
            "id",
            "name",
            "area",
            "region",
            "country",
            "status",
            "member_count",
            "my_shares",
            "my_role",
        ]

    def get_member_count(self, obj) -> int:
        return obj.memberships.count()

    def _my_membership(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        member = getattr(request.user, "member", None)
        if member is None:
            return None
        return member.group_memberships.filter(group=obj, is_active=True).first()

    def get_my_shares(self, obj) -> int:
        ms = self._my_membership(obj)
        return ms.shares_count if ms else 0

    def get_my_role(self, obj):
        ms = self._my_membership(obj)
        return ms.role if ms else None


class GroupSerializer(GroupListSerializer):
    """Full detail: includes the member list with roles/shares."""

    members = serializers.SerializerMethodField()
    created_by = MemberBriefSerializer(read_only=True, allow_null=True)
    total_shares = serializers.SerializerMethodField()

    class Meta(GroupListSerializer.Meta):
        fields = GroupListSerializer.Meta.fields + [
            "description",
            "created_by",
            "created_at",
            "total_shares",
            "members",
        ]

    def get_members(self, obj):
        return GroupMembershipSerializer(
            obj.memberships.filter(is_active=True).select_related("member"),
            many=True,
        ).data

    def get_total_shares(self, obj) -> int:
        total = obj.memberships.aggregate(total=Sum("shares_count"))["total"]
        return total or 0


class GroupActivitySerializer(serializers.ModelSerializer):
    actor = MemberBriefSerializer(read_only=True)
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = GroupActivity
        fields = [
            "id",
            "event_type",
            "event_type_display",
            "title",
            "description",
            "actor",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class GroupWorkspaceOverviewSerializer(serializers.Serializer):
    group = serializers.DictField()
    permissions = serializers.DictField()
    contribution_summary = serializers.DictField()
    loan_summary = serializers.DictField()
    recent_ledger = serializers.ListField()
    recent_activity = GroupActivitySerializer(many=True)
    pending_items = serializers.DictField()


class GroupLoanProjectionSerializer(serializers.Serializer):
    loan_number = serializers.CharField()
    borrower = MemberBriefSerializer()
    product = serializers.CharField()
    principal_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    next_repayment_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    next_due_date = serializers.DateField(allow_null=True)
    repayment_status = serializers.CharField()


class GroupRepaymentProjectionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    borrower = MemberBriefSerializer()
    loan_reference = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateTimeField()
    status = serializers.CharField()
    transaction_reference = serializers.CharField()
    description = serializers.CharField(allow_blank=True)


class GroupLedgerEntrySerializer(serializers.Serializer):
    id = serializers.CharField()
    date = serializers.DateTimeField()
    transaction_type = serializers.CharField()
    member = MemberBriefSerializer(allow_null=True)
    amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    status = serializers.CharField()
    reference = serializers.CharField(allow_blank=True)
    internal_reference = serializers.CharField(allow_blank=True)
    provider_reference = serializers.CharField(allow_blank=True, allow_null=True)
    related_contribution = serializers.IntegerField(allow_null=True)
    related_loan = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)


class GroupInvitationSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    group_id = serializers.IntegerField(source="group.id", read_only=True)

    class Meta:
        model = GroupInvitation
        fields = [
            "id",
            "group_id",
            "group_name",
            "email",
            "status",
            "token",
            "expires_at",
            "created_at",
        ]


class GroupInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()


class GroupShareSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)

    class Meta:
        model = GroupShare
        fields = [
            "id",
            "member",
            "quantity",
            "amount_paid",
            "created_at",
        ]


class GroupShareCreateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0
    )


class GroupContributionSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = GroupContribution
        fields = [
            "id",
            "member",
            "amount",
            "month",
            "reference",
            "status",
            "status_display",
            "created_at",
        ]


class GroupContributionCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    month = serializers.RegexField(regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    reference = serializers.CharField(required=False, allow_blank=True)


class GroupContributionDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[GroupContribution.Status.CONFIRMED, GroupContribution.Status.REJECTED]
    )


class MemberShareOutSerializer(serializers.ModelSerializer):
    """A member's own share-out entitlement across groups."""
    group_name = serializers.CharField(source="share_out.group.name", read_only=True)
    group_id = serializers.IntegerField(source="share_out.group_id", read_only=True)
    cycle_label = serializers.CharField(source="share_out.cycle_label", read_only=True)
    declared_at = serializers.DateField(source="share_out.declared_at", read_only=True)
    share_out_status = serializers.CharField(source="share_out.status", read_only=True)

    class Meta:
        model = MemberShareOut
        fields = [
            "id",
            "share_out",
            "group_id",
            "group_name",
            "cycle_label",
            "declared_at",
            "share_out_status",
            "amount",
            "is_paid",
            "paid_at",
        ]
        read_only_fields = fields


class ShareOutSerializer(serializers.ModelSerializer):
    """Staff view of a declared share-out with its per-member entries."""
    group_name = serializers.CharField(source="group.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    entries = MemberShareOutSerializer(many=True, read_only=True)

    class Meta:
        model = ShareOut
        fields = ["id", "group", "group_name", "cycle_label", "declared_at", "status", "status_display", "entries", "created_at"]


class ShareOutEntrySerializer(serializers.Serializer):
    membership_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class ShareOutCreateSerializer(serializers.Serializer):
    group_id = serializers.IntegerField()
    cycle_label = serializers.CharField(max_length=80)
    declared_at = serializers.DateField()
    entries = ShareOutEntrySerializer(many=True, write_only=True, allow_empty=False)

    def validate_group_id(self, value):
        group = VikobaGroup.objects.filter(pk=value).first()
        if group is None:
            raise serializers.ValidationError("Group does not exist.")
        if ShareOut.objects.filter(group_id=value, cycle_label=self.initial_data.get("cycle_label", "")).exists():
            raise serializers.ValidationError("A share-out for this cycle already exists.")
        return value


class ElectedRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ElectedRole.choices)


class CommitteeVoteSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ElectedRole.choices)
    candidate_id = serializers.UUIDField()
