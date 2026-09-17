from django.shortcuts import render
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, viewsets,  mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal

from django.utils import timezone

from .models import (
    DepositRequest,
    MembershipPlan,
    SavingsAccount,
    SavingsProduct,
    SavingsTransaction,
    WithdrawalRequest,
)
from .serializers import (
    AccountSerializer,
    DepositRequestCreateSerializer,
    DepositRequestDecisionSerializer,
    DepositRequestSerializer,
    MemberTransactionSerializer,
    MembershipPlanSerializer,
    ProductSerializer,
    TransactionCreateSerializer,
    TransactionSerializer,
    MyAccountSerializer,
    WithdrawalRequestCreateSerializer,
    WithdrawalRequestDecisionSerializer,
    WithdrawalRequestSerializer,
)
from .services import post_savings_transaction
from members.models import Member
from users.models import User
from users.notifications import notify_user
from users.permissions import HasAccountAccess, HasProductManagementAccess, HasTransactionAccess


class MyAccountsView(generics.ListAPIView):
    """Authenticated member's own savings accounts + total balance.

    Usage: GET /accounts/me/
    Returns {accounts: [...], total_balance: "..."} for the caller's Member.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MyAccountSerializer

    def list(self, request, *args, **kwargs):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"accounts": [], "total_balance": "0.00"})
        accounts = SavingsAccount.objects.filter(member=member, is_active=True).order_by("id")
        data = self.get_serializer(accounts, many=True).data
        total = sum((a.balance or Decimal("0.00")) for a in accounts)
        return Response({"accounts": data, "total_balance": str(total)})


class MemberAccountTransactionsView(generics.ListAPIView):
    """Mini-statement for one of the member's own savings accounts.

    Usage: GET /accounts/me/{account_number}/transactions/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MemberTransactionSerializer

    def get_queryset(self):
        member = getattr(self.request.user, "member", None)
        if member is None:
            return SavingsTransaction.objects.none()
        return SavingsTransaction.objects.filter(
            account__member=member,
            account__account_number=self.kwargs["account_number"],
            account__is_active=True,
        ).select_related("account").order_by("-created_at")


class MemberDepositRequestView(generics.ListCreateAPIView):
    """Member self-service deposits (M-Pesa style), pending until staff approve."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DepositRequestCreateSerializer
        return DepositRequestSerializer

    def get_queryset(self):
        member = getattr(self.request.user, "member", None)
        if member is None:
            return DepositRequest.objects.none()
        return DepositRequest.objects.filter(member=member).select_related("account", "account__product")

    def create(self, request, *args, **kwargs):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit = DepositRequest.objects.create(
            member=member,
            account=serializer.context["account"],
            amount=serializer.validated_data["amount"],
            channel=serializer.validated_data.get("channel", DepositRequest.Channel.MPESA),
            transaction_code=serializer.validated_data.get("transaction_code", ""),
        )
        return Response(DepositRequestSerializer(deposit).data, status=status.HTTP_201_CREATED)


class MemberWithdrawalRequestView(generics.ListCreateAPIView):
    """Member self-service withdrawals (verified members only)."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WithdrawalRequestCreateSerializer
        return WithdrawalRequestSerializer

    def get_queryset(self):
        member = getattr(self.request.user, "member", None)
        if member is None:
            return WithdrawalRequest.objects.none()
        return WithdrawalRequest.objects.filter(member=member).select_related("account", "account__product")

    def create(self, request, *args, **kwargs):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response(
                {"detail": "No member profile is linked to this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not member.is_verified:
            return Response(
                {
                    "detail": "Verify your account (phone, ID, next of kin and passport photo) before you can withdraw.",
                    "verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = WithdrawalRequest.objects.create(
            member=member,
            account=serializer.context["account"],
            amount=serializer.validated_data["amount"],
            narration=serializer.validated_data.get("narration", ""),
        )
        return Response(WithdrawalRequestSerializer(withdrawal).data, status=status.HTTP_201_CREATED)


class DepositRequestDecisionView(generics.GenericAPIView):
    """Staff approve/reject a member's deposit request. Approval credits the account."""

    staff_roles = {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.ACCOUNTANT}
    permission_classes = [IsAuthenticated]
    serializer_class = DepositRequestDecisionSerializer

    def post(self, request, deposit_id=None):
        if not (request.user.is_superuser or getattr(request.user, "role", None) in self.staff_roles):
            return Response({"detail": "Only staff can process deposit requests."}, status=status.HTTP_403_FORBIDDEN)
        deposit = get_object_or_404(
            DepositRequest.objects.select_related("member", "member__user", "account"),
            pk=deposit_id,
        )
        if deposit.status != DepositRequest.Status.PENDING:
            return Response({"detail": "This request has already been processed."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        decline_reason = serializer.validated_data.get("decline_reason", "")

        if decision == "approve":
            try:
                post_savings_transaction(
                    account=deposit.account,
                    transaction_type=SavingsTransaction.DEPOSIT,
                    amount=deposit.amount,
                    user=request.user,
                    narration=f"{deposit.get_channel_display()} deposit {deposit.reference}",
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            deposit.status = DepositRequest.Status.APPROVED
            deposit.processed_by = request.user
            deposit.processed_at = timezone.now()
            deposit.save(update_fields=["status", "processed_by", "processed_at"])
            member_user = getattr(deposit.member, "user", None)
            if member_user is not None:
                notify_user(
                    member_user,
                    "Deposit confirmed",
                    f"Your deposit of {deposit.amount} to {deposit.account.account_number} has been approved.",
                    kind="deposit",
                    link="/wallet",
                    sms_to=deposit.member.phone_number or None,
                )
        else:
            deposit.status = DepositRequest.Status.REJECTED
            deposit.decline_reason = decline_reason
            deposit.processed_by = request.user
            deposit.processed_at = timezone.now()
            deposit.save(update_fields=["status", "decline_reason", "processed_by", "processed_at"])
            member_user = getattr(deposit.member, "user", None)
            if member_user is not None:
                notify_user(
                    member_user,
                    "Deposit declined",
                    decline_reason or "Your deposit request was declined.",
                    kind="deposit",
                    link="/wallet",
                )

        return Response(DepositRequestSerializer(deposit).data)


class WithdrawalRequestDecisionView(generics.GenericAPIView):
    """Staff approve/reject a member's withdrawal request. Approval debits the account."""

    staff_roles = {User.ADMIN, User.MANAGER, User.OPERATION, User.FINANCE, User.ACCOUNTANT}
    permission_classes = [IsAuthenticated]
    serializer_class = WithdrawalRequestDecisionSerializer

    def post(self, request, withdrawal_id=None):
        if not (request.user.is_superuser or getattr(request.user, "role", None) in self.staff_roles):
            return Response({"detail": "Only staff can process withdrawal requests."}, status=status.HTTP_403_FORBIDDEN)
        withdrawal = get_object_or_404(
            WithdrawalRequest.objects.select_related("member", "member__user", "account"),
            pk=withdrawal_id,
        )
        if withdrawal.status != WithdrawalRequest.Status.PENDING:
            return Response({"detail": "This request has already been processed."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        decline_reason = serializer.validated_data.get("decline_reason", "")

        if decision == "approve":
            try:
                post_savings_transaction(
                    account=withdrawal.account,
                    transaction_type=SavingsTransaction.WITHDRAWAL,
                    amount=withdrawal.amount,
                    user=request.user,
                    narration=withdrawal.narration or f"Withdrawal {withdrawal.reference}",
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            withdrawal.status = WithdrawalRequest.Status.APPROVED
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.save(update_fields=["status", "processed_by", "processed_at"])
            member_user = getattr(withdrawal.member, "user", None)
            if member_user is not None:
                notify_user(
                    member_user,
                    "Withdrawal confirmed",
                    f"Your withdrawal of {withdrawal.amount} from {withdrawal.account.account_number} has been approved.",
                    kind="withdrawal",
                    link="/wallet",
                    sms_to=withdrawal.member.phone_number or None,
                )
        else:
            withdrawal.status = WithdrawalRequest.Status.REJECTED
            withdrawal.decline_reason = decline_reason
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.save(update_fields=["status", "decline_reason", "processed_by", "processed_at"])
            member_user = getattr(withdrawal.member, "user", None)
            if member_user is not None:
                notify_user(
                    member_user,
                    "Withdrawal declined",
                    decline_reason or "Your withdrawal request was declined.",
                    kind="withdrawal",
                    link="/wallet",
                )

        return Response(WithdrawalRequestSerializer(withdrawal).data)


class AccountViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    """
    A ViewSet for listing and retrieving accounts information
    """
    permission_classes = [HasAccountAccess]
    queryset = SavingsAccount.objects.all()
    serializer_class = AccountSerializer
    lookup_field = "account_number"

    @action(detail=False, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_accounts(self, request, member_id=None):
        """
        Get all accounts that belong to a specific member.
        Usage: GET /accounts/member/{member_id}/
        """
        member = get_object_or_404(Member, membership_number=member_id)
        accounts = SavingsAccount.objects.filter(member=member)
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = SavingsProduct.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [HasProductManagementAccess]


class MembershipPlanViewSet(viewsets.ModelViewSet):
    queryset = MembershipPlan.objects.filter(is_active=True).order_by("price")
    serializer_class = MembershipPlanSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        # create/update/delete only staff
        from users.permissions import HasProductManagementAccess as _Staff
        return [_Staff()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    A ViewSet for managing transactions with security features.
    
    List: GET /transactions/?account=SA00000001&transaction_type=deposit
    Create: POST /transactions/
    Retrieve: GET /transactions/{id}/
    """
    permission_classes = [HasTransactionAccess]
    queryset = SavingsTransaction.objects.select_related('account', 'account__member', 'performed_by').all()
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        """
        Filter transactions by account number and/or transaction type
        """
        queryset = super().get_queryset()
        
        # Filter by account number
        account_number = self.request.query_params.get('account', None)
        if account_number:
            queryset = queryset.filter(account__account_number=account_number)
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        Create a new transaction using the post_savings_transaction service.
        This ensures all business logic and security measures are applied.
        """
        # Validate input
        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Get the account
            account = SavingsAccount.objects.get(
                account_number=serializer.validated_data['account_number']
            )
            
            # Create the transaction using the service
            transaction = post_savings_transaction(
                account=account,
                transaction_type=serializer.validated_data['transaction_type'],
                amount=Decimal(str(serializer.validated_data['amount'])),
                user=request.user,
                narration=serializer.validated_data.get('narration', '')
            )
            
            # Return the created transaction
            output_serializer = TransactionSerializer(transaction)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            
        except SavingsAccount.DoesNotExist:
            return Response(
                {'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'An error occurred while processing the transaction'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='account/(?P<account_number>[^/.]+)')
    def account_transactions(self, request, account_number=None):
        """
        Get all transactions for a specific account.
        Usage: GET /transactions/account/{account_number}/
        """
        account = get_object_or_404(SavingsAccount, account_number=account_number)
        transactions = SavingsTransaction.objects.filter(account=account).select_related(
            'account', 'account__member', 'performed_by'
        )
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_transactions(self, request, member_id=None):
        """
        Get all transactions for a specific member.
        Usage: GET /transactions/member/{member_id}
        """
        member = get_object_or_404(Member, membership_number=member_id)
        transactions = SavingsTransaction.objects.filter(account__member=member).select_related(
            'account', 'account__member', 'performed_by'
        )
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
