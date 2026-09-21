"""Finance API views.

Staff get a read-only view of accounts, ledgers and audit history plus two
write operations: posting a balanced manual journal and reversing a transaction
(both go through the engine — there is no raw ORM write path in the API).

Members get a strictly scoped read of their own financial transactions.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from finance.models import AuditEvent, FinancialAccount, FinancialTransaction
from finance.services.engine import FinancialError
from finance.services.reversals import reverse_financial_transaction
from users.permissions import ALL_BUSINESS_ROLES, HasTransactionAccess, IsMember, has_role

from .serializers import (
    AuditEventSerializer,
    FinancialAccountSerializer,
    FinancialTransactionSerializer,
    JournalRequestSerializer,
    ReversalRequestSerializer,
)


class _StaffOrOwnMemberReadOnlyMixin:
    """Role staff may read everything; a member may only read their own."""

    def _scope_queryset(self, queryset):
        user = self.request.user
        if user.is_authenticated and has_role(user, ALL_BUSINESS_ROLES):
            return queryset
        if user.is_authenticated and user.role == "ME" and getattr(user, "member", None):
            return queryset.filter(member=user.member)
        return queryset.none()

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [HasTransactionAccess()]


class FinancialAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FinancialAccountSerializer
    lookup_field = "account_number"
    permission_classes = [HasTransactionAccess]

    def get_queryset(self):
        qs = FinancialAccount.objects.select_related("member", "group").order_by("account_number")
        account_type = self.request.query_params.get("type")
        if account_type:
            qs = qs.filter(account_type=account_type)
        return qs


class FinancialTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FinancialTransactionSerializer
    lookup_field = "reference"

    def get_queryset(self):
        user = self.request.user
        qs = (
            FinancialTransaction.objects.select_related(
                "group", "member", "initiated_by", "reversal_of"
            )
            .prefetch_related("entries", "entries__account", "reversals")
            .order_by("-created_at")
        )
        if not has_role(user, ALL_BUSINESS_ROLES):
            if user.role == "ME" and getattr(user, "member", None):
                qs = qs.filter(member=user.member)
            else:
                qs = qs.none()

        reference = self.request.query_params.get("reference")
        if reference:
            qs = qs.filter(reference=reference)
        txn_type = self.request.query_params.get("type")
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        group = self.request.query_params.get("group")
        if group:
            qs = qs.filter(group_id=group)
        member = self.request.query_params.get("member")
        if member and has_role(user, ALL_BUSINESS_ROLES):
            qs = qs.filter(member_id=member)
        return qs

    @action(detail=True, methods=["post"])
    def reverse(self, request, reference=None):
        """Reverse a transaction (staff only). The original stays intact."""
        if not has_role(request.user, ALL_BUSINESS_ROLES):
            return Response({"detail": "You do not have permission."}, status=status.HTTP_403_FORBIDDEN)
        fin_tx = get_object_or_404(FinancialTransaction, reference=reference)
        serializer = ReversalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reversal = reverse_financial_transaction(
                fin_tx=fin_tx,
                reason=serializer.validated_data["reason"],
                actor=request.user,
                audit_ip=_client_ip(request),
            )
        except FinancialError as exc:
            return Response({"code": exc.code, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(reversal).data,
            status=status.HTTP_201_CREATED,
        )


class JournalView(viewsets.ViewSet):
    """Staff-only manual balanced journal (adjustment, group expense, transfer, refund)."""

    permission_classes = [HasTransactionAccess]

    @transaction.atomic
    def create(self, request):
        from finance.services.engine import post_transaction

        serializer = JournalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            fin_tx, created = post_transaction(
                transaction_type=data["transaction_type"],
                amount=data["amount"],
                currency=data["currency"],
                description=data.get("description", ""),
                entries=data["entries"],
                idempotency_key=data.get("idempotency_key") or None,
                initiated_by=request.user,
                audit_ip=_client_ip(request),
            )
        except FinancialError as exc:
            return Response({"code": exc.code, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        output = FinancialTransactionSerializer(fin_tx, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [HasTransactionAccess]

    def get_queryset(self):
        return AuditEvent.objects.select_related("user", "transaction").order_by("-created_at")


class MemberFinancialTransactionsView(viewsets.ReadOnlyModelViewSet):
    """A member's own financial transactions (read-only, strictly scoped)."""

    serializer_class = FinancialTransactionSerializer
    permission_classes = [IsMember]
    lookup_field = "reference"

    def get_queryset(self):
        member = self.request.user.member
        qs = (
            FinancialTransaction.objects.filter(member=member)
            .select_related("group", "initiated_by", "reversal_of")
            .prefetch_related("entries", "entries__account", "reversals")
            .order_by("-created_at")
        )
        reference = self.request.query_params.get("reference")
        if reference:
            qs = qs.filter(reference=reference)
        return qs


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")[:45]