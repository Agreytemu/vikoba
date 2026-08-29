import logging

from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from members.models import Member
from .models import (
    ElectedRole,
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
    GroupContributionCreateSerializer,
    GroupContributionDecisionSerializer,
    GroupContributionSerializer,
    GroupCreateSerializer,
    GroupInvitationSerializer,
    GroupInviteSerializer,
    GroupListSerializer,
    GroupSerializer,
    GroupShareCreateSerializer,
    GroupShareSerializer,
    MemberShareOutSerializer,
    ShareOutCreateSerializer,
    ShareOutSerializer,
)

logger = logging.getLogger(__name__)

STAFF_ROLES = {"AD", "MA", "OP", "FI", "LO", "AC"}


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
            return Response([], status=status.HTTP_200_OK)
        contributions = group.contributions.filter(member=member)
        return Response(
            GroupContributionSerializer(contributions, many=True).data,
            status=status.HTTP_200_OK,
        )

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