"""Governance API: approval inbox, approve/reject/cancel, policy configuration."""
from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from governance import workflow
from governance.errors import ApprovalError
from governance.models import ApprovalAction, ApprovalRequest, ApprovalStatus, GroupWithdrawalPolicy
from governance.serializers import (
    ApprovalActionSerializer,
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    GroupWithdrawalPolicySerializer,
)
from groups.models import VikobaGroup
from payments.errors import PaymentError


class ApprovalInboxView(GenericAPIView):
    """List approval requests (the officer inbox), group-scoped on the backend.

    Platform officers see all groups; committee officers see their own groups;
    members see their own requests. Filters: type, status, group, min/max
    amount.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalRequestSerializer

    def get(self, request):
        params = request.query_params
        user = request.user

        statuses = params.get("status")
        statuses = [s for s in (statuses.split(",") if statuses else [ApprovalStatus.PENDING]) if s]

        try:
            qs = workflow.approval_inbox(
                user,
                request_type=params.get("type") or None,
                statuses=statuses,
            )
        except ValueError:
            return Response({"detail": "Invalid filter."}, status=status.HTTP_400_BAD_REQUEST)

        group = params.get("group")
        if group:
            qs = qs.filter(group_id=group)

        amount_min = params.get("amount_min")
        amount_max = params.get("amount_max")
        if amount_min:
            try:
                qs = qs.filter(amount__gte=float(amount_min))
            except (TypeError, ValueError):
                return Response({"detail": "amount_min must be numeric."}, status=status.HTTP_400_BAD_REQUEST)
        if amount_max:
            try:
                qs = qs.filter(amount__lte=float(amount_max))
            except (TypeError, ValueError):
                return Response({"detail": "amount_max must be numeric."}, status=status.HTTP_400_BAD_REQUEST)

        qs = qs.order_by("-created_at")
        serializer = ApprovalRequestSerializer(qs[:300], many=True, context={"request": request})
        return Response(serializer.data)


class ApprovalDetailView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalRequestSerializer

    def get_object(self, user):
        request = get_object_or_404(
            ApprovalRequest.objects.select_related("requester", "group").prefetch_related("steps"),
            pk=self.kwargs.get("approval_id"),
        )
        if not workflow.visible_request(user, request):
            from rest_framework.exceptions import NotFound

            raise NotFound("Approval request not found.")
        return request

    def get(self, request, approval_id=None):
        approval = self.get_object(request.user)
        return Response(ApprovalRequestSerializer(approval, context={"request": request}).data)


class ApprovalActionView(GenericAPIView):
    """POST approve|reject|cancel against a pending approval request."""

    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalDecisionSerializer

    def _instance(self, user):
        approval = get_object_or_404(
            ApprovalRequest.objects.select_related("requester", "group"),
            pk=self.kwargs.get("approval_id"),
        )
        if not workflow.visible_request(user, approval):
            from rest_framework.exceptions import NotFound

            raise NotFound("Approval request not found.")
        return approval

    def post(self, request, approval_id=None):
        approval = self._instance(request.user)
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        ip = request.META.get("REMOTE_ADDR")

        try:
            if action == "approve":
                result = workflow.approve(request=approval, user=request.user, reason=reason, ip=ip)
            elif action == "reject":
                result = workflow.reject(request=approval, user=request.user, reason=reason, ip=ip)
            else:
                result = workflow.cancel(request=approval, user=request.user, reason=reason, ip=ip)
        except ApprovalError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except PaymentError as exc:
            return Response({"detail": exc.message, "code": getattr(exc, "code", "PAYMENT_ERROR")}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(ApprovalRequestSerializer(result, context={"request": request}).data)


class ApprovalHistoryView(GenericAPIView):
    """Audit trail for one approval request (system + human decisions)."""

    permission_classes = [IsAuthenticated]
    serializer_class = ApprovalActionSerializer

    def get(self, request, approval_id=None):
        approval = get_object_or_404(ApprovalRequest, pk=approval_id)
        if not workflow.visible_request(request.user, approval):
            from rest_framework.exceptions import NotFound

            raise NotFound("Approval request not found.")
        actions = ApprovalAction.objects.filter(request_id=approval.pk).order_by("created_at", "id")
        return Response(ApprovalActionSerializer(actions, many=True).data)


class GroupWithdrawalPolicyView(GenericAPIView):
    """Read/update a group's withdrawal policy.

    Reads: committee officers + staff. Updates: committee officers
    (Treasurer/Chairperson/Secretary) of that group or platform staff. Policy
    changes are audited through an ApprovalAction record.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = GroupWithdrawalPolicySerializer

    def _authorize(self, user, group, require_write=False):
        if user.is_superuser or user.role in workflow.SYSTEM_OFFICER_ROLES:
            return True
        from governance import workflow as _w

        if require_write:
            return _w.satisfies_role(user, group, "TREASURER") or _w.satisfies_role(
                user, group, "CHAIRPERSON"
            ) or _w.satisfies_role(user, group, "SECRETARY")
        return _w.satisfies_role(user, group, "TREASURER") or _w.satisfies_role(
            user, group, "CHAIRPERSON"
        ) or _w.satisfies_role(user, group, "SECRETARY")

    def get(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        if not self._authorize(request.user, group):
            return Response({"detail": "Not authorized to view this group's withdrawal policy."}, status=status.HTTP_403_FORBIDDEN)
        policy = GroupWithdrawalPolicy.objects.filter(group=group).first()
        if policy is None:
            policy = GroupWithdrawalPolicy.objects.create(group=group)
        return Response(GroupWithdrawalPolicySerializer(policy).data)

    def put(self, request, group_id=None):
        group = get_object_or_404(VikobaGroup, pk=group_id)
        if not self._authorize(request.user, group, require_write=True):
            return Response({"detail": "Only committee officers or staff can update the withdrawal policy."}, status=status.HTTP_403_FORBIDDEN)

        policy, _ = GroupWithdrawalPolicy.objects.get_or_create(group=group)
        serializer = GroupWithdrawalPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save(updated_by=request.user)

        audit = ApprovalAction.objects.create(
            request=None,
            actor=request.user,
            actor_type=ApprovalAction.ACTOR_HUMAN,
            action="policy_changed",
            from_status="",
            to_status="",
            decision=None,
            reason=f"Withdrawal policy for {group.name} updated by {request.user.get_full_name() or request.user.email}.",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return Response(GroupWithdrawalPolicySerializer(policy).data)