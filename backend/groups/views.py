import logging

from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from loans.models import LoanAccount, LoanSchedule, LoanTransaction
from members.models import Member
from payments.models import PaymentTransaction
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
from .serializers import (
    CommitteeVoteSerializer,
    ElectedRoleSerializer,
    GroupActivitySerializer,
    GroupContributionCreateSerializer,
    GroupContributionDecisionSerializer,
    GroupContributionSerializer,
    GroupCreateSerializer,
    GroupInvitationSerializer,
    GroupInviteSerializer,
    GroupListSerializer,
    GroupLoanProjectionSerializer,
    GroupLedgerEntrySerializer,
    GroupMembershipSerializer,
    GroupRepaymentProjectionSerializer,
    GroupSerializer,
    GroupShareCreateSerializer,
    GroupShareSerializer,
    MemberShareOutSerializer,
    ShareOutCreateSerializer,
    ShareOutSerializer,
)

logger = logging.getLogger(__name__)

STAFF_ROLES = {"AD", "MA", "OP", "FI", "LO", "AC"}
COMMITTEE_ROLES = {
    GroupMembership.Role.CHAIRPERSON,
    GroupMembership.Role.SECRETARY,
    GroupMembership.Role.TREASURER,
}


def _member_for(request):
    """The authenticated member's profile, or None when not linked."""
    try:
        member = request.user.member
        return member if request.user.is_authenticated else None
    except Member.DoesNotExist:
        return None


def _active_membership(group, member):
    if member is None:
        return None
    return group.memberships.filter(member=member, is_active=True).first()


def _is_staff(user):
    return bool(user and (getattr(user, "is_staff", False) or getattr(user, "role", None) in STAFF_ROLES))


def _group_member_ids(group):
    return list(
        group.memberships.filter(is_active=True).values_list("member_id", flat=True)
    )


def _require_group_member(request, group):
    member = _member_for(request)
    membership = _active_membership(group, member)
    if member is None or membership is None:
        raise PermissionDenied("You are not a member of this group.")
    return member, membership


def _can_manage_group(user, membership):
    return _is_staff(user) or (membership and membership.role in COMMITTEE_ROLES)


def _record_activity(group, event_type, title, *, actor=None, description="", **metadata):
    return GroupActivity.objects.create(
        group=group,
        actor=actor,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata,
    )


def _paginate_queryset(request, queryset, serializer_class):
    page = max(int(request.query_params.get("page", 1) or 1), 1)
    page_size = min(max(int(request.query_params.get("page_size", 20) or 20), 1), 50)
    start = (page - 1) * page_size
    end = start + page_size
    return Response(
        {
            "count": queryset.count(),
            "page": page,
            "page_size": page_size,
            "results": serializer_class(queryset[start:end], many=True).data,
        },
        status=status.HTTP_200_OK,
    )


def _member_brief_dict(member):
    from .serializers import MemberBriefSerializer

    return MemberBriefSerializer(member).data if member is not None else None


def _loan_projection(loan):
    next_installment = (
        loan.schedule.filter(is_paid=False).order_by("due_date", "installment_number").first()
    )
    outstanding = (loan.outstanding_principal or Decimal("0")) + (
        loan.outstanding_interest or Decimal("0")
    )
    return {
        "loan_number": loan.loan_number,
        "borrower": _member_brief_dict(loan.member),
        "product": loan.product.name,
        "principal_amount": loan.principal_amount,
        "outstanding_amount": outstanding,
        "status": loan.status,
        "next_repayment_amount": next_installment.total_due if next_installment else None,
        "next_due_date": next_installment.due_date if next_installment else None,
        "repayment_status": "paid_up" if next_installment is None else "due",
    }


def _ledger_entries_for_group(group, *, limit=None):
    member_ids = _group_member_ids(group)
    members = {
        m.pk: m
        for m in Member.objects.filter(pk__in=member_ids).select_related("user")
    }
    entries = []

    for contribution in group.contributions.select_related("member")[:200]:
        entries.append(
            {
                "id": f"contribution-{contribution.pk}",
                "date": contribution.created_at,
                "transaction_type": "Contribution",
                "member": _member_brief_dict(contribution.member),
                "amount": contribution.amount,
                "status": contribution.status,
                "reference": contribution.reference or "",
                "internal_reference": "",
                "provider_reference": "",
                "related_contribution": contribution.pk,
                "related_loan": "",
                "description": f"Contribution for {contribution.month}",
            }
        )

    for share in group.shares.select_related("member")[:200]:
        entries.append(
            {
                "id": f"share-{share.pk}",
                "date": share.created_at,
                "transaction_type": "Share Purchase",
                "member": _member_brief_dict(share.member),
                "amount": share.amount_paid,
                "status": "RECORDED",
                "reference": f"HISA-{share.pk}",
                "internal_reference": "",
                "provider_reference": "",
                "related_contribution": None,
                "related_loan": "",
                "description": f"{share.quantity} hisa purchased",
            }
        )

    for tx in PaymentTransaction.objects.filter(group=group).select_related(
        "member", "contribution", "loan"
    )[:200]:
        entries.append(
            {
                "id": f"payment-{tx.pk}",
                "date": tx.completed_at or tx.created_at,
                "transaction_type": tx.get_transaction_type_display(),
                "member": _member_brief_dict(tx.member),
                "amount": tx.amount,
                "status": tx.status,
                "reference": tx.internal_reference,
                "internal_reference": tx.internal_reference,
                "provider_reference": tx.provider_reference,
                "related_contribution": tx.contribution_id,
                "related_loan": tx.loan.loan_number if tx.loan_id else "",
                "description": tx.metadata.get("purpose", "") if isinstance(tx.metadata, dict) else "",
            }
        )

    loan_transactions = LoanTransaction.objects.filter(
        loan__member_id__in=member_ids
    ).select_related("loan", "loan__member")[:200]
    for loan_tx in loan_transactions:
        entries.append(
            {
                "id": f"loan-transaction-{loan_tx.pk}",
                "date": loan_tx.created_at,
                "transaction_type": "Loan Repayment"
                if loan_tx.transaction_type == LoanTransaction.REPAYMENT
                else "Loan Disbursement"
                if loan_tx.transaction_type == LoanTransaction.DISBURSEMENT
                else loan_tx.get_transaction_type_display(),
                "member": _member_brief_dict(loan_tx.loan.member),
                "amount": loan_tx.amount,
                "status": "POSTED",
                "reference": loan_tx.reference,
                "internal_reference": loan_tx.reference,
                "provider_reference": "",
                "related_contribution": None,
                "related_loan": loan_tx.loan.loan_number,
                "description": loan_tx.narration,
            }
        )

    for entry in MemberShareOut.objects.filter(
        share_out__group=group
    ).select_related("member", "share_out")[:200]:
        entries.append(
            {
                "id": f"share-out-{entry.pk}",
                "date": entry.paid_at or timezone.make_aware(datetime.combine(entry.share_out.declared_at, time.min)),
                "transaction_type": "Share-out",
                "member": _member_brief_dict(entry.member),
                "amount": entry.amount,
                "status": "PAID" if entry.is_paid else entry.share_out.status,
                "reference": f"SHAREOUT-{entry.share_out_id}-{entry.pk}",
                "internal_reference": "",
                "provider_reference": "",
                "related_contribution": None,
                "related_loan": "",
                "description": entry.share_out.cycle_label,
            }
        )

    entries.sort(key=lambda item: item["date"], reverse=True)
    return entries[:limit] if limit else entries


class GroupListView(generics.ListCreateAPIView):
    """My groups, plus create a new verified group."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GroupCreateSerializer
        return GroupListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        member = _member_for(self.request)
        if member is None:
            return VikobaGroup.objects.none()
        return (
            member.group_memberships.filter(is_active=True)
            .select_related("group")
            .values_list("group", flat=True)
        )

    def list(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None:
            return Response([], status=status.HTTP_200_OK)
        groups = VikobaGroup.objects.filter(
            id__in=self.get_queryset()
        ).prefetch_related("memberships")
        serializer = GroupListSerializer(groups, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_count = VikobaGroup.objects.filter(created_by=member).count()
        group_limit = 1 if not member.is_verified else 3
        if created_count >= group_limit:
            return Response(
                {
                    "detail": (
                        f"You have reached the limit of {group_limit} group"
                        f"{'' if group_limit == 1 else 's'} per member."
                        + ("" if member.is_verified else " Get verified to create up to 3 groups.")
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.save(created_by=member)
        GroupMembership.objects.create(
            group=group, member=member, role=GroupMembership.Role.CHAIRPERSON
        )
        _record_activity(
            group,
            GroupActivity.Type.MEMBER_JOINED,
            "Group created",
            actor=member,
            description=f"{member.first_name} {member.last_name}".strip() + " created the group.",
        )
        out = GroupSerializer(group, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)


class GroupDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GroupSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_object(self):
        group = get_object_or_404(VikobaGroup, pk=self.kwargs["group_id"])
        member = _member_for(self.request)
        if member is None or _active_membership(group, member) is None:
            raise PermissionDenied("You are not a member of this group.")
        return group


class GroupWorkspaceOverviewView(generics.GenericAPIView):
    """Read-only workspace summary for one group."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(
            VikobaGroup.objects.prefetch_related("memberships"),
            pk=group_id,
        )
        member, membership = _require_group_member(request, group)
        member_ids = _group_member_ids(group)

        contribution_totals = group.contributions.aggregate(
            total=Sum("amount"),
            count=Count("id"),
        )
        confirmed = group.contributions.filter(
            status=GroupContribution.Status.CONFIRMED
        ).aggregate(total=Sum("amount"), count=Count("id"))
        pending = group.contributions.filter(
            status=GroupContribution.Status.PENDING
        ).aggregate(total=Sum("amount"), count=Count("id"))

        loans = LoanAccount.objects.filter(member_id__in=member_ids)
        outstanding = loans.aggregate(
            principal=Sum("outstanding_principal"),
            interest=Sum("outstanding_interest"),
        )
        loan_summary = {
            "loan_count": loans.count(),
            "active_count": loans.filter(status=LoanAccount.DISBURSED).count(),
            "outstanding_total": (outstanding["principal"] or Decimal("0"))
            + (outstanding["interest"] or Decimal("0")),
            "next_due_count": LoanSchedule.objects.filter(
                loan__member_id__in=member_ids,
                is_paid=False,
                due_date__lte=timezone.now().date(),
            ).count(),
        }

        payload = {
            "group": {
                "id": group.pk,
                "code": f"GRP-{group.pk:05d}",
                "name": group.name,
                "area": group.area,
                "region": group.region,
                "country": group.country,
                "description": group.description,
                "status": group.status,
                "member_count": group.memberships.filter(is_active=True).count(),
                "my_role": membership.role,
                "total_shares": group.memberships.aggregate(total=Sum("shares_count"))["total"] or 0,
                "created_at": group.created_at,
            },
            "permissions": {
                "can_manage": _can_manage_group(request.user, membership),
                "can_invite": True,
                "can_view_financials": True,
            },
            "contribution_summary": {
                "total_amount": contribution_totals["total"] or Decimal("0"),
                "total_count": contribution_totals["count"] or 0,
                "confirmed_amount": confirmed["total"] or Decimal("0"),
                "confirmed_count": confirmed["count"] or 0,
                "pending_amount": pending["total"] or Decimal("0"),
                "pending_count": pending["count"] or 0,
            },
            "loan_summary": loan_summary,
            "recent_ledger": _ledger_entries_for_group(group, limit=5),
            "recent_activity": GroupActivitySerializer(
                group.activities.select_related("actor")[:6],
                many=True,
            ).data,
            "pending_items": {
                "pending_contributions": pending["count"] or 0,
                "pending_invitations": group.invitations.filter(
                    status=GroupInvitation.Status.PENDING,
                    expires_at__gt=timezone.now(),
                ).count(),
            },
        }
        return Response(payload, status=status.HTTP_200_OK)


class GroupMembersView(generics.GenericAPIView):
    """Searchable, paginated group membership view."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        _require_group_member(request, group)
        queryset = group.memberships.select_related("member", "member__user")

        search = request.query_params.get("search", "").strip()
        role = request.query_params.get("role", "").strip()
        active = request.query_params.get("active", "true").lower()

        if active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)
        if role:
            queryset = queryset.filter(role=role)
        if search:
            queryset = queryset.filter(
                Q(member__first_name__icontains=search)
                | Q(member__last_name__icontains=search)
                | Q(member__membership_number__icontains=search)
            )
        return _paginate_queryset(request, queryset.order_by("joined_at"), GroupMembershipSerializer)


class GroupLoansView(generics.GenericAPIView):
    """Read-only projection of loans belonging to members of this group."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        _require_group_member(request, group)
        member_ids = _group_member_ids(group)
        queryset = (
            LoanAccount.objects.filter(member_id__in=member_ids)
            .select_related("member", "member__user", "product")
            .prefetch_related("schedule")
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status", "").strip()
        search = request.query_params.get("search", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(
                Q(loan_number__icontains=search)
                | Q(member__first_name__icontains=search)
                | Q(member__last_name__icontains=search)
                | Q(member__membership_number__icontains=search)
            )

        page = max(int(request.query_params.get("page", 1) or 1), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20) or 20), 1), 50)
        rows = [_loan_projection(loan) for loan in queryset[(page - 1) * page_size : page * page_size]]
        return Response(
            {
                "count": queryset.count(),
                "page": page,
                "page_size": page_size,
                "results": GroupLoanProjectionSerializer(rows, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupRepaymentsView(generics.GenericAPIView):
    """Read-only projection of loan repayment transactions for group members."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        _require_group_member(request, group)
        queryset = (
            LoanTransaction.objects.filter(
                loan__member_id__in=_group_member_ids(group),
                transaction_type=LoanTransaction.REPAYMENT,
            )
            .select_related("loan", "loan__member", "loan__member__user")
            .order_by("-created_at")
        )
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search)
                | Q(loan__loan_number__icontains=search)
                | Q(loan__member__membership_number__icontains=search)
            )

        rows = [
            {
                "id": item.pk,
                "borrower": _member_brief_dict(item.loan.member),
                "loan_reference": item.loan.loan_number,
                "amount": item.amount,
                "date": item.created_at,
                "status": "POSTED",
                "transaction_reference": item.reference,
                "description": item.narration,
            }
            for item in queryset
        ]
        page = max(int(request.query_params.get("page", 1) or 1), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20) or 20), 1), 50)
        start = (page - 1) * page_size
        return Response(
            {
                "count": len(rows),
                "page": page,
                "page_size": page_size,
                "results": GroupRepaymentProjectionSerializer(rows[start : start + page_size], many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupLedgerView(generics.GenericAPIView):
    """Read-only ledger projection from existing financial records."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        _require_group_member(request, group)
        entries = _ledger_entries_for_group(group)
        search = request.query_params.get("search", "").strip().lower()
        type_filter = request.query_params.get("type", "").strip().lower()
        status_filter = request.query_params.get("status", "").strip().lower()

        if search:
            entries = [
                entry for entry in entries
                if search in (entry["reference"] or "").lower()
                or search in (entry["description"] or "").lower()
                or (
                    entry["member"]
                    and search in f"{entry['member'].get('first_name', '')} {entry['member'].get('last_name', '')} {entry['member'].get('membership_number', '')}".lower()
                )
            ]
        if type_filter:
            entries = [entry for entry in entries if entry["transaction_type"].lower() == type_filter]
        if status_filter:
            entries = [entry for entry in entries if entry["status"].lower() == status_filter]

        page = max(int(request.query_params.get("page", 1) or 1), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20) or 20), 1), 50)
        start = (page - 1) * page_size
        return Response(
            {
                "count": len(entries),
                "page": page,
                "page_size": page_size,
                "results": GroupLedgerEntrySerializer(entries[start : start + page_size], many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class GroupActivityListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        _require_group_member(request, group)
        queryset = group.activities.select_related("actor", "actor__user").all()
        event_type = request.query_params.get("event_type", "").strip()
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return _paginate_queryset(request, queryset, GroupActivitySerializer)


class GroupInviteView(generics.GenericAPIView):
    """Invite someone by email (verified members only). Sends the code email."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupInviteSerializer

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _active_membership(group, member) is None:
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        if group.invitations.filter(
            email=email, status=GroupInvitation.Status.PENDING
        ).exists():
            return Response(
                {"detail": "This email already has a pending invitation."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Member.objects.filter(email=email).exists() and _active_membership(group, Member.objects.get(email=email)):
            return Response(
                {"detail": "This member is already in the group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = group.invitations.create(
            email=email, invited_by=member
        )
        _record_activity(
            group,
            GroupActivity.Type.MEMBER_INVITED,
            "Member invited",
            actor=member,
            description=f"{email} was invited to join the group.",
            email=email,
        )
        from .emails import send_group_invite_email

        send_group_invite_email(invitation)
        return Response(
            GroupInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED,
        )


class GroupPendingInvitationsView(generics.GenericAPIView):
    """Pending invitations for the authenticated member's email."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None or not member.email:
            return Response([], status=status.HTTP_200_OK)
        invitations = GroupInvitation.objects.filter(
            email=member.email.lower(),
            status=GroupInvitation.Status.PENDING,
            expires_at__gt=timezone.now(),
        ).select_related("group")
        return Response(
            GroupInvitationSerializer(invitations, many=True).data,
            status=status.HTTP_200_OK,
        )


class GroupJoinView(generics.GenericAPIView):
    """Accept an invitation using its token (no verified requirement to enter)."""

    permission_classes = [IsAuthenticated]
    serializer_class = None

    def post(self, request, group_id=None, *args, **kwargs):
        token = (request.data or {}).get("token")
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._join(member, token, group_id, request)

    def _join(self, member, token, group_id=None, request=None):
        if not token:
            return Response(
                {"detail": "Invitation token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = (
            GroupInvitation.objects.filter(
                token=token, status=GroupInvitation.Status.PENDING
            )
            .select_for_update()
            .first()
        )
        if invitation is None or invitation.is_expired:
            if invitation is not None:
                invitation.status = GroupInvitation.Status.EXPIRED
                invitation.save(update_fields=["status"])
            return Response(
                {"detail": "This invitation is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.email.strip().lower() != member.email.lower():
            return Response(
                {"detail": "This invitation belongs to a different email account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        group = invitation.group
        if group_id is not None and group.pk != int(group_id):
            return Response(
                {"detail": "This invitation does not match the requested group."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if group.status == VikobaGroup.Status.CLOSED:
            return Response(
                {"detail": "This group is closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership, created = GroupMembership.objects.get_or_create(
            group=group,
            member=member,
            defaults={"role": GroupMembership.Role.MEMBER},
        )
        if not created:
            membership.is_active = True
            membership.save(update_fields=["is_active"])

        invitation.status = GroupInvitation.Status.ACCEPTED
        invitation.save(update_fields=["status"])
        _record_activity(
            group,
            GroupActivity.Type.MEMBER_JOINED,
            "Member joined",
            actor=member,
            description=f"{member.first_name} {member.last_name}".strip() + " joined the group.",
            membership_id=membership.pk,
        )
        return Response(
            GroupSerializer(
                group,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class GroupAcceptInviteView(generics.GenericAPIView):
    """Accept an invitation by token alone (used by emailed invite links)."""

    permission_classes = [IsAuthenticated]
    serializer_class = None

    def post(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = (request.data or {}).get("token")
        result = GroupJoinView()._join(member, token, request=request)
        return result


class GroupSharesView(generics.GenericAPIView):
    """Buy hisa in the group."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupShareCreateSerializer

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership = _active_membership(group, member)
        if membership is None:
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        share = GroupShare.objects.create(
            group=group,
            member=member,
            quantity=serializer.validated_data["quantity"],
            amount_paid=serializer.validated_data.get("amount_paid", 0),
        )
        membership.shares_count += share.quantity
        membership.save(update_fields=["shares_count"])
        _record_activity(
            group,
            GroupActivity.Type.SHARE_PURCHASED,
            "Hisa recorded",
            actor=member,
            description=f"{member.first_name} {member.last_name}".strip() + f" recorded {share.quantity} hisa.",
            share_id=share.pk,
            quantity=share.quantity,
        )
        return Response(
            GroupShareSerializer(share).data,
            status=status.HTTP_201_CREATED,
        )


class GroupContributionsView(generics.GenericAPIView):
    """Add a contribution (members can; pending until staff confirms)."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupContributionCreateSerializer

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member = _member_for(request)
        if member is None or _active_membership(group, member) is None:
            raise PermissionDenied("You are not a member of this group.")
        contributions = group.contributions.select_related("member", "member__user")
        membership = _active_membership(group, member)
        if not _can_manage_group(request.user, membership):
            contributions = contributions.filter(member=member)

        search = request.query_params.get("search", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        month = request.query_params.get("month", "").strip()
        date_from = request.query_params.get("date_from", "").strip()
        date_to = request.query_params.get("date_to", "").strip()
        if status_filter:
            contributions = contributions.filter(status=status_filter)
        if month:
            contributions = contributions.filter(month=month)
        if date_from:
            contributions = contributions.filter(created_at__date__gte=date_from)
        if date_to:
            contributions = contributions.filter(created_at__date__lte=date_to)
        if search:
            contributions = contributions.filter(
                Q(reference__icontains=search)
                | Q(member__first_name__icontains=search)
                | Q(member__last_name__icontains=search)
                | Q(member__membership_number__icontains=search)
            )
        return _paginate_queryset(request, contributions.order_by("-created_at"), GroupContributionSerializer)

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _active_membership(group, member) is None:
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contribution = GroupContribution.objects.create(
            group=group,
            member=member,
            amount=serializer.validated_data["amount"],
            month=serializer.validated_data["month"],
            reference=serializer.validated_data.get("reference", ""),
        )
        _record_activity(
            group,
            GroupActivity.Type.CONTRIBUTION_RECORDED,
            "Contribution recorded",
            actor=member,
            description=f"Contribution for {contribution.month} was recorded.",
            contribution_id=contribution.pk,
            status=contribution.status,
        )
        return Response(
            GroupContributionSerializer(contribution).data,
            status=status.HTTP_201_CREATED,
        )


class GroupContributionDecisionView(generics.GenericAPIView):
    """Staff confirms or rejects a contribution."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupContributionDecisionSerializer

    def _is_staff(self, request):
        user = request.user
        return user.is_staff or user.role in STAFF_ROLES

    def post(self, request, group_id=None, contribution_id=None):
        if not self._is_staff(request):
            return Response(
                {"detail": "Only staff can confirm contributions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        group = get_object_or_404(VikobaGroup, pk=group_id)
        contribution = get_object_or_404(group.contributions, pk=contribution_id)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        contribution.status = serializer.validated_data["status"]
        contribution.confirmed_by = request.user
        contribution.save(update_fields=["status", "confirmed_by"])
        _record_activity(
            group,
            GroupActivity.Type.CONTRIBUTION_UPDATED,
            "Contribution status updated",
            actor=_member_for(request),
            description=f"Contribution {contribution.pk} was marked {contribution.status}.",
            contribution_id=contribution.pk,
            status=contribution.status,
        )

        # When a contribution is confirmed, deliver a receipt to the contributor
        # from the group chair's WhatsApp device (falling back to the admin
        # device). Delivery failure never blocks the staff confirmation itself.
        if contribution.status == "CONFIRMED":
            from whatsapp.service import deliver_receipt

            try:
                deliver_receipt(contribution)
            except Exception:  # pragma: no cover - bridge outages must not fail confirms
                logger.exception("Receipt delivery failed for contribution %s", contribution.id)

        return Response(
            GroupContributionSerializer(contribution).data,
            status=status.HTTP_200_OK,
        )


class MemberShareOutListView(generics.ListAPIView):
    """The authenticated member's own share-out entitlements across groups."""

    permission_classes = [IsAuthenticated]
    serializer_class = MemberShareOutSerializer

    def get_queryset(self):
        member = _member_for(self.request)
        if member is None:
            return MemberShareOut.objects.none()
        return (
            MemberShareOut.objects.filter(member=member)
            .select_related("share_out", "share_out__group")
            .order_by("-share_out__declared_at")
        )


class ShareOutListView(generics.ListAPIView):
    """Staff list all share-outs."""

    permission_classes = [IsAuthenticated]
    serializer_class = ShareOutSerializer

    def get_queryset(self):
        if self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.role in STAFF_ROLES
        ):
            return ShareOut.objects.select_related("group").prefetch_related("entries__member").order_by("-declared_at")
        return ShareOut.objects.none()


class ShareOutCreateView(generics.GenericAPIView):
    """Staff declare a share-out with per-member entitlements."""

    permission_classes = [IsAuthenticated]
    serializer_class = ShareOutCreateSerializer

    def post(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.role in STAFF_ROLES):
            return Response({"detail": "Only staff can declare share-outs."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = VikobaGroup.objects.get(pk=data["group_id"])

        entries = data["entries"]
        numbers = [entry["membership_number"] for entry in entries]
        members = Member.objects.filter(membership_number__in=numbers)
        by_number = {m.membership_number: m for m in members}
        missing = set(numbers) - set(by_number)
        if missing:
            return Response(
                {"detail": f"Unknown members: {', '.join(sorted(missing))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        share_out = ShareOut.objects.create(
            group=group,
            cycle_label=data["cycle_label"],
            declared_at=data["declared_at"],
            created_by=request.user,
        )
        MemberShareOut.objects.bulk_create(
            [
                MemberShareOut(share_out=share_out, member=by_number[entry["membership_number"]], amount=entry["amount"])
                for entry in entries
            ]
        )

        for entry in entries:
            member = by_number[entry["membership_number"]]
            user = getattr(member, "user", None)
            if user is not None:
                from users.notifications import notify_user

                notify_user(
                    user,
                    "Share-out declared",
                    f"{group.name} declared a share-out of {entry['amount']} for cycle {data['cycle_label']}.",
                    kind="share_out",
                    link="/share-outs",
                    sms_to=member.phone_number or None,
                )

        return Response(
            ShareOutSerializer(
                ShareOut.objects.select_related("group").prefetch_related("entries__member").get(pk=share_out.pk)
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ShareOutPayView(generics.GenericAPIView):
    """Staff mark one member's share-out entitlement as paid."""

    permission_classes = [IsAuthenticated]

    def post(self, request, share_out_id=None, membership_number=None):
        if not (request.user.is_staff or request.user.role in STAFF_ROLES):
            return Response({"detail": "Only staff can pay share-outs."}, status=status.HTTP_403_FORBIDDEN)
        entry = get_object_or_404(
            MemberShareOut.objects.select_related("share_out", "member"),
            share_out_id=share_out_id,
            member__membership_number=membership_number,
        )
        if entry.is_paid:
            return Response({"detail": "This entitlement is already paid."}, status=status.HTTP_400_BAD_REQUEST)
        entry.is_paid = True
        entry.paid_at = timezone.now()
        entry.paid_by = request.user
        entry.save(update_fields=["is_paid", "paid_at", "paid_by"])

        from users.notifications import notify_user

        user = getattr(entry.member, "user", None)
        if user is not None:
            notify_user(
                user,
                "Share-out paid",
                f"Your {entry.amount} share-out from {entry.share_out.group.name} has been paid out.",
                kind="share_out",
                link="/share-outs",
                sms_to=entry.member.phone_number or None,
            )
        return Response(MemberShareOutSerializer(entry).data, status=status.HTTP_200_OK)


def _committee_access(request, group):
    """Active membership guard shared by all committee endpoints."""
    member = _member_for(request)
    if member is None:
        return None, Response(
            {"detail": "No member profile is linked to this account."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if _active_membership(group, member) is None:
        return None, Response(
            {"detail": "You are not a member of this group."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return member, None


def _member_brief(member):
    from .serializers import MemberBriefSerializer

    if member is None:
        return None
    return MemberBriefSerializer(member).data


def _candidates_for(group, role, member):
    """Candidates for the role with tallies plus what the member input."""
    candidates = list(
        GroupRoleCandidate.objects.filter(group=group, role=role)
        .select_related("member")
        .order_by("declared_at")
    )
    counts = {
        row["candidate"]: row["n"]
        for row in GroupRoleVote.objects.filter(group=group, role=role)
        .values("candidate")
        .annotate(n=Count("id"))
    }
    my_vote = (
        GroupRoleVote.objects.filter(group=group, role=role, voter=member)
        .values_list("candidate_id", flat=True)
        .first()
    )
    my_candidacy_ids = set(
        GroupRoleCandidate.objects.filter(group=group, member=member, role=role)
        .values_list("member_id", flat=True)
    )
    return {
        "role": role,
        "open": bool(candidates),
        "candidates": [
            {
                "member": _member_brief(c.member),
                "member_id": str(c.member_id),
                "votes": counts.get(c.member_id, 0),
                "declared_at": c.declared_at.isoformat(),
            }
            for c in candidates
        ],
        "my_vote": str(my_vote) if my_vote else None,
        "my_candidacy": member.pk in my_candidacy_ids,
    }


class GroupCommitteeView(generics.GenericAPIView):
    """Current committee: chairperson, elected officers, candidates and votes."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member, err = _committee_access(request, group)
        if err is not None:
            return err

        memberships = {
            m.role: m
            for m in group.memberships.filter(is_active=True).select_related("member")
        }
        committee = {
            "chairperson": memberships.get(GroupMembership.Role.CHAIRPERSON),
            "treasurer": memberships.get(GroupMembership.Role.TREASURER),
            "secretary": memberships.get(GroupMembership.Role.SECRETARY),
        }
        my_role = memberships.get(GroupMembership.Role.CHAIRPERSON) is not None

        def role_data(role):
            return _candidates_for(group, role, member)

        data = {
            "chairperson": _member_brief(
                getattr(committee["chairperson"], "member", None)
            ),
            "treasurer": _member_brief(getattr(committee["treasurer"], "member", None)),
            "secretary": _member_brief(getattr(committee["secretary"], "member", None)),
            "is_chairperson": my_role,
            "roles": {
                ElectedRole.TREASURER: role_data(ElectedRole.TREASURER),
                ElectedRole.SECRETARY: role_data(ElectedRole.SECRETARY),
            },
        }
        return Response(data, status=status.HTTP_200_OK)


class GroupCommitteeDeclareView(generics.GenericAPIView):
    """A verified member declares interest to run for treasurer or secretary."""

    permission_classes = [IsAuthenticated]
    serializer_class = ElectedRoleSerializer

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member, err = _committee_access(request, group)
        if err is not None:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]

        if not member.is_verified:
            return Response(
                {"detail": "Only verified members can run for a committee position."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if group.memberships.filter(
            is_active=True, role=role
        ).exists():
            return Response(
                {"detail": "This position already has an elected officer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidate, created = GroupRoleCandidate.objects.get_or_create(
            group=group, member=member, role=role
        )
        return Response(
            {"role": role, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class GroupCommitteeVoteView(generics.GenericAPIView):
    """Cast or change my vote for a candidate standing for an elected role."""

    permission_classes = [IsAuthenticated]
    serializer_class = CommitteeVoteSerializer

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        voter, err = _committee_access(request, group)
        if err is not None:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        candidate = get_object_or_404(Member, pk=serializer.validated_data["candidate_id"])

        if group.memberships.filter(is_active=True, role=role).exists():
            return Response(
                {"detail": "This position is already decided for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if _active_membership(group, candidate) is None:
            return Response(
                {"detail": "You can only vote for a candidate who is in this group."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not GroupRoleCandidate.objects.filter(
            group=group, member=candidate, role=role
        ).exists():
            return Response(
                {"detail": "This member has not declared interest for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        GroupRoleVote.objects.update_or_create(
            group=group, role=role, voter=voter, defaults={"candidate": candidate}
        )
        return Response(
            {"role": role, "candidate_id": str(candidate.pk)},
            status=status.HTTP_200_OK,
        )


class GroupCommitteeCloseView(generics.GenericAPIView):
    """Chairperson confirms the vote result: the top candidate takes the role."""

    permission_classes = [IsAuthenticated]
    serializer_class = ElectedRoleSerializer

    def post(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        member, err = _committee_access(request, group)
        if err is not None:
            return err
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]

        membership = _active_membership(group, member)
        if not membership or membership.role != GroupMembership.Role.CHAIRPERSON:
            return Response(
                {"detail": "Only the chairperson can confirm the vote result."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if group.memberships.filter(is_active=True, role=role).exists():
            return Response(
                {"detail": "This position is already decided for this role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tally = list(
            GroupRoleVote.objects.filter(group=group, role=role)
            .values("candidate")
            .annotate(votes=Count("id"))
            .order_by("-votes", "candidate")
        )
        if not tally:
            return Response(
                {"detail": "No votes have been cast for this role yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        winner_id = tally[0]["candidate"]
        winner = group.memberships.get(member_id=winner_id)

        winner.role = role
        winner.save(update_fields=["role"])
        GroupRoleCandidate.objects.filter(group=group, role=role).delete()
        GroupRoleVote.objects.filter(group=group, role=role).delete()
        _record_activity(
            group,
            GroupActivity.Type.ROLE_CHANGED,
            "Committee role assigned",
            actor=member,
            description=f"{winner.member} was assigned {role}.",
            member=str(winner.member_id),
            role=role,
        )

        from users.notifications import notify_user

        user = getattr(winner.member, "user", None)
        if user is not None:
            notify_user(
                user,
                "Committee election result",
                f"You have been elected {role.title()} of {group.name}.",
                kind="group",
                link=f"/groups/{group.pk}",
                sms_to=winner.member.phone_number or None,
            )
        return Response(
            {"role": role, "member": _member_brief(winner.member)},
            status=status.HTTP_200_OK,
        )


class GroupDashboardSummaryView(generics.GenericAPIView):
    """Member dashboard aggregates: hisa owned, contributions and hisa value."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        member = _member_for(request)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        memberships = member.group_memberships.filter(is_active=True)
        total_shares = memberships.aggregate(total=Sum("shares_count"))["total"] or 0

        shares_value = (
            member.group_shares.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
        )
        hisa_value = (
            (shares_value / Decimal(total_shares))
            if total_shares
            else Decimal("0")
        )

        def _sum_for(status_val):
            row = member.group_contributions.filter(status=status_val).aggregate(
                total=Sum("amount")
            )
            return row["total"] or Decimal("0")

        payload = {
            "total_shares": total_shares,
            "hisa_value": hisa_value,
            "contributed_total": _sum_for(GroupContribution.Status.CONFIRMED),
            "contributed_pending": _sum_for(GroupContribution.Status.PENDING),
            "group_count": memberships.count(),
            "created_count": VikobaGroup.objects.filter(created_by=member).count(),
        }
        return Response(payload, status=status.HTTP_200_OK)
