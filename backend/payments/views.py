from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
import decimal

from payments.errors import PaymentError
from payments.models import PaymentTransaction, ReconciliationRecord, WebhookEvent
from payments.serializers import (
    MemberSubscriptionSerializer,
    PayWithdrawalSerializer,
    PaymentTransactionSerializer,
    ReconciliationRecordSerializer,
    WebhookPayloadSerializer,
)
from payments.services.payment_service import (
    initiate_contribution_payment,
    initiate_loan_repayment,
    initiate_savings_deposit,
    initiate_subscription_payment,
)
from payments.services.payout_service import auto_withdraw, initiate_withdrawal_payout
from payments.utils.phone import detect_network, normalize_phone
from payments.webhooks.snippe import WebhookDispatcher, WebhookVerificationError, WebhookVerifier
from accounts.models import MembershipPlan, MemberSubscription, SavingsAccount, WithdrawalRequest
from accounts.serializers import WithdrawalRequestSerializer
from groups.models import VikobaGroup
from loans.models import LoanAccount


User = get_user_model()
STAFF_ROLES = {
    User.ADMIN,
    User.MANAGER,
    User.OPERATION,
    User.FINANCE,
    User.ACCOUNTANT,
}

MIN_PAYMENT_TZS = 500
MIN_PAYOUT_TZS = 5000
# Snippe mobile-money networks a member may pick for a payout (disbursement).
PAYOUT_NETWORKS = {"mpesa", "airtel", "mixx", "halotel"}
# Roles allowed to resolve a reconciliation exception (writes audit trail).
RECONCILIATION_RESOLVER_ROLES = {
    User.ADMIN,
    User.MANAGER,
}


def _payment_initiation_failure(exc):
    """Map service exceptions to a structured, client-safe error response.

    Provider messages must never leak to the client: the client always gets a
    stable code + generic detail; the provider detail lives in server logs.
    """
    if isinstance(exc, PaymentError):
        code = exc.code
        detail = exc.message
        http_status = (
            status.HTTP_502_BAD_GATEWAY
            if code in (PaymentError.PROVIDER_TIMEOUT, PaymentError.PROVIDER_ERROR)
            else status.HTTP_400_BAD_REQUEST
        )
        return Response({"code": code, "detail": detail}, status=http_status)
    return Response(
        {
            "code": "PROVIDER_ERROR",
            "detail": "The payment provider could not complete this request. Please try again.",
        },
        status=status.HTTP_502_BAD_GATEWAY,
    )


# ---------------------------------------------------------------------------
# Member-initiated collections
# ---------------------------------------------------------------------------

class SavingsDepositPaymentView(APIView):
    """Member tops up their own savings account via Snippe mobile money.

    The account is credited automatically when the payment.completed webhook
    arrives — no staff approval is involved.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)

        amount = request.data.get("amount")
        phone = request.data.get("phone", "") or member.phone_number or ""

        try:
            amount = decimal.Decimal(str(amount))
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Response({"detail": "amount must be numeric."}, status=status.HTTP_400_BAD_REQUEST)
        if amount < MIN_PAYMENT_TZS:
            return Response(
                {"detail": f"Minimum Snippe payment is {MIN_PAYMENT_TZS} TZS."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tx = initiate_savings_deposit(member=member, amount=amount, phone=phone)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # provider errors must not 500 the member page
            return _payment_initiation_failure(exc)

        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class ContributionPaymentView(APIView):
    """Member pays a group contribution by initiating a mobile-money payment."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)

        group_id = request.data.get("group_id")
        amount = request.data.get("amount")
        month = request.data.get("month")
        phone = request.data.get("phone", "") or member.phone_number or ""

        group = get_object_or_404(VikobaGroup, pk=group_id)

        try:
            amount = decimal.Decimal(str(amount))
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Response({"detail": "amount must be numeric."}, status=status.HTTP_400_BAD_REQUEST)
        if amount < MIN_PAYMENT_TZS:
            return Response(
                {"detail": f"Minimum Snippe payment is {MIN_PAYMENT_TZS} TZS."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # A member paying a group must be a member of that group.
        if not group.memberships.filter(member=member).exists():
            return Response(
                {"detail": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            tx = initiate_contribution_payment(
                member=member,
                group=group,
                amount=amount,
                month=month,
                phone=phone,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # provider errors must not 500 the member page
            return _payment_initiation_failure(exc)

        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class LoanRepaymentPaymentView(APIView):
    """Member initiates a mobile-money repayment for one loan installment."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)

        loan = get_object_or_404(
            LoanAccount.objects.select_related("member"),
            loan_number=request.data.get("loan_number"),
            member=member,
        )
        installment_number = request.data.get("installment_number")
        phone = request.data.get("phone", "") or member.phone_number or ""

        try:
            tx = initiate_loan_repayment(
                member=member,
                loan=loan,
                installment_number=int(installment_number),
                phone=phone,
            )
        except (ValueError, TypeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _payment_initiation_failure(exc)
        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Staff-triggered disbursements (withdrawals via Snippe)
# ---------------------------------------------------------------------------

class WithdrawalPayoutView(APIView):
    """Staff sends an approved withdrawal payout via Snippe mobile money."""

    permission_classes = [IsAuthenticated]

    def post(self, request, withdrawal_id=None):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) in STAFF_ROLES):
            return Response({"detail": "Staff role required."}, status=status.HTTP_403_FORBIDDEN)

        withdrawal = get_object_or_404(
            WithdrawalRequest.objects.select_related("member", "member__user", "account"),
            pk=withdrawal_id,
        )
        if withdrawal.status != WithdrawalRequest.Status.APPROVED:
            return Response(
                {"detail": "Withdrawal must be approved before payout dispatch."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if withdrawal.amount < MIN_PAYOUT_TZS:
            return Response(
                {"detail": f"Minimum Snippe payout is {MIN_PAYOUT_TZS} TZS."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PayWithdrawalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tx = initiate_withdrawal_payout(withdrawal=withdrawal)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _payment_initiation_failure(exc)

        return Response(PaymentTransactionSerializer(tx).data)


class AutoWithdrawalView(APIView):
    """Member withdrawal that the system approves and dispatches by itself.

    No staff step: the balance is validated here, the request is recorded as
    APPROVED and the Snippe payout fires immediately. The ledger is debited only
    once the payout.completed webhook confirms the money actually left.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)

        if not member.is_verified:
            return Response(
                {
                    "detail": "Verify your account (phone, ID, next of kin and passport photo) before you can withdraw.",
                    "verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        from kyc import services as kyc_services

        if not kyc_services.satisfies(member):
            return Response(
                {
                    "detail": "Your KYC verification level does not yet meet the requirement for withdrawals.",
                    "verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not member.phone_verified:
            return Response(
                {
                    "detail": "Verify your phone number before you can withdraw.",
                    "verification_required": True,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        account_number = request.data.get("account_number")
        amount = request.data.get("amount")
        narration = request.data.get("narration", "") or ""
        # Withdrawals are locked to the member's verified number — a client can
        # never redirect the payout to a different mobile-money number.
        phone = member.phone_number or ""

        # The member picks the network the payout settles on (M-Pesa, Airtel,
        # Mixx or Halotel). Default to the one matching the verified number.
        raw_network = (request.data.get("network") or "").strip().lower()
        if raw_network and raw_network not in PAYOUT_NETWORKS:
            return Response(
                {"detail": "Unknown payment network. Choose M-Pesa, Airtel Money, Mixx by Yas or Halotel."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        network = raw_network or detect_network(member.phone_number) or "mpesa"

        try:
            amount = decimal.Decimal(str(amount))
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Response({"detail": "amount must be numeric."}, status=status.HTTP_400_BAD_REQUEST)
        if amount < MIN_PAYOUT_TZS:
            return Response(
                {"detail": f"Minimum Snippe payout is {MIN_PAYOUT_TZS} TZS."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account = get_object_or_404(
            SavingsAccount.objects.select_related("product"),
            account_number=account_number,
            member=member,
        )

        try:
            # Phase 4: the governance engine auto-adjudicates (AUTO_APPROVED /
            # MANUAL_REVIEW / REJECTED) after validating the member, the group,
            # the balance (with reservations) and the configurable policy.
            from governance.errors import ApprovalError
            from governance.withdrawals import submit_withdrawal

            result = submit_withdrawal(
                member=member,
                account=account,
                amount=amount,
                narration=narration,
                network=network,
                requester=request.user,
            )
        except ApprovalError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _payment_initiation_failure(exc)

        payload = {
            "withdrawal": WithdrawalRequestSerializer(result.withdrawal).data,
            "decision": result.decision,
            "decision_reason": result.reason,
            "review_required": result.review_required,
        }
        if result.payout is not None:
            payload["payout"] = PaymentTransactionSerializer(result.payout).data
        if result.approval is not None:
            payload["approval_id"] = result.approval.pk
        status_code = status.HTTP_202_ACCEPTED if result.review_required else status.HTTP_201_CREATED
        return Response(payload, status=status_code)


# ---------------------------------------------------------------------------
# Plan subscription checkout
# ---------------------------------------------------------------------------

class SubscriptionCheckoutView(APIView):
    """Member pays for their chosen subscription plan via Snippe mobile money.

    The plan (and therefore the price) is resolved from the database — the
    amount is never read from the client. A PENDING subscription is created
    and is only activated when the verified ``payment.completed`` webhook
    arrives.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)

        plan_id = request.data.get("plan_id")
        plan = get_object_or_404(MembershipPlan, pk=plan_id, is_active=True)
        payment_method = request.data.get("payment_method", "") or ""
        phone = request.data.get("phone", "") or member.phone_number or ""
        full_name = request.data.get("full_name", "") or f"{member.first_name} {member.last_name}".strip()
        email = request.data.get("email", "") or member.email or ""

        normalized = normalize_phone(phone)
        if not normalized:
            return Response(
                {"detail": "Enter a valid Tanzanian mobile-money number (e.g. +255712345678)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tx = initiate_subscription_payment(
                member=member,
                plan=plan,
                phone=normalized,
                payment_method=payment_method,
                full_name=full_name,
                email=email,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return _payment_initiation_failure(exc)

        return Response(
            {
                "transaction": PaymentTransactionSerializer(tx).data,
                "subscription": MemberSubscriptionSerializer(tx.subscription).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MySubscriptionView(APIView):
    """The authenticated member's most recent subscription (with plan detail)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)
        subscription = (
            MemberSubscription.objects.filter(member=member)
            .select_related("plan")
            .order_by("-created_at", "-pk")
            .first()
        )
        if subscription is None:
            return Response({"detail": "No subscription found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(MemberSubscriptionSerializer(subscription).data)


# ---------------------------------------------------------------------------
# Transaction status (member reads its own)
# ---------------------------------------------------------------------------

class PaymentTransactionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, internal_reference=None):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)
        tx = get_object_or_404(
            PaymentTransaction.objects.select_related("member", "group", "contribution", "loan", "withdrawal"),
            internal_reference=internal_reference,
            member=member,
        )
        return Response(PaymentTransactionSerializer(tx).data)


class MyPaymentTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = getattr(request.user, "member", None)
        if member is None:
            return Response({"detail": "Member account required."}, status=status.HTTP_403_FORBIDDEN)
        txs = PaymentTransaction.objects.filter(member=member).select_related(
            "group", "contribution", "loan", "withdrawal"
        )[:100]
        return Response(PaymentTransactionSerializer(txs, many=True).data)


# ---------------------------------------------------------------------------
# Reconciliation (staff): every financial mismatch surfaces here, nothing is
# silently corrected. Only an authorised resolution closes a record.
# ---------------------------------------------------------------------------

class ReconciliationListView(APIView):
    """Staff: list reconciliation exceptions (OPEN by default)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) in STAFF_ROLES):
            return Response({"detail": "Staff role required."}, status=status.HTTP_403_FORBIDDEN)
        resolution = (request.query_params.get("resolution", "OPEN") or "OPEN").upper()
        qs = ReconciliationRecord.objects.select_related("payment", "resolved_by")
        if resolution in ("OPEN", "RESOLVED"):
            qs = qs.filter(resolution_status=resolution)
        return Response(ReconciliationRecordSerializer(qs, many=True).data)


class ReconciliationResolveView(APIView):
    """Admin/manager closes an OPEN reconciliation exception.

    Resolving never rewrites financial history: it records the decision, who
    made it and why, and writes a finance audit event. Any money correction
    (post or reverse) is a separate, documented ledger action.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) in RECONCILIATION_RESOLVER_ROLES):
            return Response({"detail": "Admin or manager role required."}, status=status.HTTP_403_FORBIDDEN)
        record = get_object_or_404(
            ReconciliationRecord.objects.select_related("payment"),
            pk=pk,
            resolution_status=ReconciliationRecord.ResolutionStatus.OPEN,
        )
        note = (request.data.get("resolution_note") or "").strip()
        if not note:
            return Response(
                {"detail": "A resolution note is required and becomes part of the audit trail."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record.resolution_status = ReconciliationRecord.ResolutionStatus.RESOLVED
        record.resolved_by = user
        record.resolved_at = timezone.now()
        record.resolution_note = note
        record.save(
            update_fields=["resolution_status", "resolved_by", "resolved_at", "resolution_note"]
        )

        try:
            from finance.models import AuditEvent

            AuditEvent.objects.create(
                user=user,
                action="payment.reconciliation.resolved",
                reference=record.internal_reference or record.provider_reference,
                metadata={
                    "reconciliation_record": record.pk,
                    "issue_type": record.issue_type,
                    "provider_reference": record.provider_reference,
                    "resolution_note": note,
                },
            )
        except Exception:
            pass  # audit must never block the resolution response

        return Response(ReconciliationRecordSerializer(record).data)


# ---------------------------------------------------------------------------
# Webhook ingress (unauthenticated by design; validated by signature)
# ---------------------------------------------------------------------------

@csrf_exempt
@api_view(["POST"])
@permission_classes([])
def snippe_webhook(request):
    raw_body = request.body.decode("utf-8", errors="replace")
    verifier = WebhookVerifier()
    try:
        verifier.verify(
            request.headers.get("X-Webhook-Signature", ""),
            request.headers.get("X-Webhook-Timestamp", ""),
            raw_body,
        )
    except WebhookVerificationError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = WebhookPayloadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
    except Exception:
        return Response({"detail": "Malformed webhook payload."}, status=status.HTTP_400_BAD_REQUEST)

    event_id = str(data.get("id") or "")
    if not event_id:
        return Response({"detail": "Missing event id."}, status=status.HTTP_400_BAD_REQUEST)

    event, created = WebhookEvent.objects.get_or_create(
        event_id=event_id,
        defaults={
            "event_type": str(data.get("type") or ""),
            "api_version": str(data.get("api_version") or ""),
            "payload": data,
        },
    )
    if not created:
        # Duplicate delivery — acknowledged without reprocessing.
        _record_already_processed_event(event, data)
        return Response({"status": "duplicate", "already_processed": event.processed})

    try:
        WebhookDispatcher().dispatch(event, data)
    except Exception:
        event.processed = False
        event.save(update_fields=["processed"])
        return Response(
            {"detail": "Webhook processed with error; will retry."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"status": "processed"})


def _record_already_processed_event(event, data):
    """Note re-delivered webhook ids so the ops dashboard can see them.

    The ingress acknowledges the duplicate without reprocessing; the record is
    informational and must never fail the acknowledgement.
    """
    body = data.get("data") if isinstance(data.get("data"), dict) else data
    reference = str(body.get("reference") or "")
    if not reference:
        return
    try:
        ReconciliationRecord.objects.get_or_create(
            provider="snippe",
            provider_reference=reference,
            issue_type=ReconciliationRecord.IssueType.ALREADY_PROCESSED_EVENT,
            defaults={
                "event_id": event.event_id,
                "actual_status": str(data.get("type") or ""),
                "notes": "A webhook event id was delivered more than once; the payment was not reprocessed.",
            },
        )
    except Exception:  # noqa: BLE001
        pass  # acknowledgement of a duplicate must never fail