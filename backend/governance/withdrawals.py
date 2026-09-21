"""Automated withdrawal engine.

Routes every member withdrawal through the governance engine:

    submit -> validate member/account -> reserve funds (row lock)
           -> policy evaluate -> AUTO_APPROVED | MANUAL_REVIEW | REJECTED

* ``AUTO_APPROVED``: records the system decision, approves, reserves the funds
  (WithdrawalRequest status APPROVED), and immediately dispatches the Snippe
  payout. The ledger debit still happens exactly once, on ``payout.completed``.
* ``MANUAL_REVIEW``: the request stays PENDING (funds reserved by status) and
  appears in the officer approval inbox. Human approval later dispatches it.
* ``REJECTED``: the request is closed with the decision reason.

Reservation: while a request carries status PENDING/APPROVED/SENT_TO_SNIPPE,
its amount is excluded from the member's available balance.  The account row is
locked with ``select_for_update`` while writing, so two simultaneous withdrawal
requests can never both spend the same money.

Execution of human/system decisions is delegated back from
:mod:`governance.workflow` through :func:`execute_request`.
"""
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import SavingsAccount, WithdrawalRequest
from governance import workflow
from governance.errors import ApprovalError
from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    Decision,
    RequestType,
    RequiredLevel,
)
from governance.policy import get_or_create_policy, evaluate_withdrawal
from payments.services.payout_service import _payout_key, initiate_withdrawal_payout
from payments.services.snippe import MIN_PAYOUT

logger = logging.getLogger("governance")

# Statuses that hold a fund reservation for the account.
ACTIVE_RESERVATION_STATUSES = (
    WithdrawalRequest.Status.PENDING,
    WithdrawalRequest.Status.APPROVED,
    WithdrawalRequest.Status.SENT_TO_SNIPPE,
)
# The pledge is released on these terminal statuses.
RELEASED_STATUSES = (
    WithdrawalRequest.Status.SUCCESS,
    WithdrawalRequest.Status.FAILED,
    WithdrawalRequest.Status.REJECTED,
    WithdrawalRequest.Status.CANCELLED,
)


@dataclass
class SubmitResult:
    """Outcome of :func:`submit_withdrawal`."""

    withdrawal: WithdrawalRequest
    decision: Decision
    reason: str
    approval: ApprovalRequest | None = None
    payout: object | None = None
    review_required: bool = False

    @property
    def is_auto(self):
        return self.decision == Decision.AUTO_APPROVED

    @property
    def is_review(self):
        return self.decision == Decision.MANUAL_REVIEW


def _default_group(member):
    membership = member.group_memberships.filter(is_active=True).order_by("joined_at").first()
    return membership.group if membership else None


def reserved_total(account: SavingsAccount, *, exclude_pk=None) -> Decimal:
    """Sum of amounts already reserved by other active withdrawal requests."""
    rows = WithdrawalRequest.objects.filter(
        account_id=account.pk,
        status__in=ACTIVE_RESERVATION_STATUSES,
    )
    if exclude_pk is not None:
        rows = rows.exclude(pk=exclude_pk)
    return sum((row.amount for row in rows.only("amount")), Decimal("0.00"))


def available_balance(account: SavingsAccount, *, exclude_pk=None) -> Decimal:
    """Authoritative available balance: ledger-synced balance minus active
    reservations. Call under the account row lock for a deterministic answer."""
    return Decimal(str(account.balance or "0")) - reserved_total(account, exclude_pk=exclude_pk)


def request_for(withdrawal) -> ApprovalRequest | None:
    from django.contrib.contenttypes.models import ContentType

    return (
        ApprovalRequest.objects.filter(
            content_type=ContentType.objects.get_for_model(WithdrawalRequest),
            object_id=withdrawal.pk,
        )
        .select_related("group")
        .first()
    )


def submit_withdrawal(
    *,
    member,
    account,
    amount,
    narration="",
    network="",
    requester=None,
    group=None,
    policy=None,
    expires_hours=None,
):
    """Create + auto-adjudicate a withdrawal through the governance engine."""
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ApprovalError(ApprovalError.INVALID_AMOUNT, "Amount must be positive.")

    if not member.is_verified:
        raise ApprovalError(ApprovalError.KYC_REQUIRED, "Withdrawals require a verified account.")

    requester = requester or getattr(member, "user", None)
    group = group or _default_group(member)
    policy = policy if policy is not None else (get_or_create_policy(group) if group else None)

    with db_transaction.atomic():
        acct = SavingsAccount.objects.select_for_update().select_related("product").get(pk=account.pk)
        if not acct.is_active:
            raise ApprovalError(ApprovalError.MEMBER_NOT_ACTIVE, "Account is not active.")
        if not acct.product.allows_withdrawals:
            raise ApprovalError(ApprovalError.POLICY_FAILED, "Withdrawals are not allowed on this account.")

        withdrawal = WithdrawalRequest.objects.create(
            member=member,
            account=acct,
            amount=amount,
            narration=narration,
        )

        available = available_balance(acct, exclude_pk=withdrawal.pk)
        decision = evaluate_withdrawal(
            member=member,
            account=acct,
            group=group,
            amount=amount,
            available_balance=available,
            policy=policy,
        )

        if decision.is_rejected:
            withdrawal.status = WithdrawalRequest.Status.REJECTED
            withdrawal.decline_reason = decision.reason
            withdrawal.save(update_fields=["status", "decline_reason"])
            approval = workflow.create_request(
                group=group,
                request_type=RequestType.WITHDRAWAL,
                resource=withdrawal,
                requester=requester,
                amount=amount,
                required_level=RequiredLevel.MANUAL,
                decision=Decision.REJECTED,
                decision_reason=decision.reason,
                rules_passed=decision.rules_passed,
                policy_version=decision.policy_version,
                metadata={"network": network, "code": decision.code},
            )
            approval.status = ApprovalStatus.REJECTED
            approval.save(update_fields=["status"])
            workflow.record_action(
                request=approval,
                action=ApprovalAction.ACTION_REJECT,
                from_status=ApprovalStatus.PENDING,
                to_status=ApprovalStatus.REJECTED,
                actor=None,
                actor_type=ApprovalAction.ACTOR_SYSTEM,
                decision=Decision.REJECTED,
                reason=decision.reason,
            )
            _notify(member, "Withdrawal declined", decision.reason, "withdrawal")
            raise ApprovalError(decision.code or ApprovalError.POLICY_FAILED, decision.reason)

        if decision.is_review:
            approval = workflow.create_request(
                group=group,
                request_type=RequestType.WITHDRAWAL,
                resource=withdrawal,
                requester=requester,
                amount=amount,
                required_level=RequiredLevel.MULTI if decision.review_levels == "TWO_LEVEL" else RequiredLevel.MANUAL,
                required_role=decision.required_role,
                review_roles=_review_roles(decision),
                decision=Decision.MANUAL_REVIEW,
                decision_reason=decision.reason,
                rules_passed=decision.rules_passed,
                policy_version=decision.policy_version,
                metadata={"network": network, "code": decision.code, "manual_review_rules": decision.failed_rules},
                expires_at=timezone.now() + _expiry_timedelta(expires_hours),
            )
            workflow.record_action(
                request=approval,
                action=ApprovalAction.ACTION_REVIEW_REQUIRED,
                from_status=ApprovalStatus.PENDING,
                to_status=ApprovalStatus.PENDING,
                actor=None,
                actor_type=ApprovalAction.ACTOR_SYSTEM,
                decision=Decision.MANUAL_REVIEW,
                reason=decision.reason,
            )
            _notify(member, "Withdrawal needs review", decision.reason, "withdrawal")
            _notify_officers(group, approval)
            return SubmitResult(
                withdrawal=withdrawal,
                decision=Decision.MANUAL_REVIEW,
                reason=decision.reason,
                approval=approval,
                review_required=True,
            )

        # AUTO_APPROVED
        withdrawal.status = WithdrawalRequest.Status.APPROVED
        withdrawal.save(update_fields=["status"])
        approval = workflow.create_request(
            group=group,
            request_type=RequestType.WITHDRAWAL,
            resource=withdrawal,
            requester=requester,
            amount=amount,
            required_level=RequiredLevel.AUTOMATIC,
            decision=Decision.AUTO_APPROVED,
            decision_reason=decision.reason,
            rules_passed=decision.rules_passed,
            policy_version=decision.policy_version,
            metadata={"network": network},
        )
        approval.status = ApprovalStatus.APPROVED
        approval.save(update_fields=["status", "decision"])
        workflow.record_action(
            request=approval,
            action=ApprovalAction.ACTION_AUTO_APPROVE,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.APPROVED,
            actor=None,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            decision=Decision.AUTO_APPROVED,
            reason=decision.reason,
        )

        payout = None
        if amount >= MIN_PAYOUT:
            payout = _dispatch_payout(withdrawal, network)
            workflow.mark_processing(approval, reason="Snippe payout initiated.")
        else:
            approval.status = ApprovalStatus.COMPLETED
            approval.save(update_fields=["status"])
            workflow.record_action(
                request=approval,
                action=ApprovalAction.ACTION_COMPLETE,
                from_status=ApprovalStatus.APPROVED,
                to_status=ApprovalStatus.COMPLETED,
                actor=None,
                actor_type=ApprovalAction.ACTOR_SYSTEM,
                reason="Below Snippe payout minimum; completed as officer-handled.",
            )
        return SubmitResult(
            withdrawal=withdrawal,
            decision=Decision.AUTO_APPROVED,
            reason=decision.reason,
            approval=approval,
            payout=payout,
            review_required=False,
        )


def _dispatch_payout(withdrawal, network):
    return initiate_withdrawal_payout(withdrawal=withdrawal, network=network or "mpesa")


def _review_roles(decision):
    if getattr(decision, "review_levels", "SINGLE") == "TWO_LEVEL":
        return ["TREASURER", "CHAIRPERSON"]
    return [decision.required_role or "TREASURER"]


def _expiry_timedelta(expires_hours=None):
    from datetime import timedelta

    from django.conf import settings

    hours = expires_hours if expires_hours is not None else getattr(settings, "APPROVAL_EXPIRY_HOURS", 72)
    return timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Executor (called by governance.workflow on human decisions)
# ---------------------------------------------------------------------------

def execute_request(request: ApprovalRequest):
    """Route a resolved approval request to its domain executor."""
    if request.request_type != RequestType.WITHDRAWAL:
        return
    withdrawal = request.resource
    if withdrawal is None:
        return

    if request.status == ApprovalStatus.APPROVED and request.decision in (Decision.AUTO_APPROVED, Decision.MANUAL_REVIEW):
        _complete_approved(withdrawal, request)
    elif request.status == ApprovalStatus.REJECTED:
        _complete_rejected(withdrawal, request)
    elif request.status in (ApprovalStatus.CANCELLED, ApprovalStatus.EXPIRED):
        _complete_cancelled(withdrawal, request)


def _complete_approved(withdrawal, request):
    """Execute an approved withdrawal: mark APPROVED and dispatch to Snippe."""
    if withdrawal.status not in (
        WithdrawalRequest.Status.PENDING,
        WithdrawalRequest.Status.APPROVED,
    ):
        return
    if withdrawal.status != WithdrawalRequest.Status.APPROVED:
        withdrawal.status = WithdrawalRequest.Status.APPROVED
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=["status", "processed_at"])

    amount = Decimal(str(withdrawal.amount))
    if amount >= MIN_PAYOUT:
        _dispatch_payout(withdrawal, request.metadata.get("network") or "")
        if request.status == ApprovalStatus.APPROVED:
            from governance.models import ApprovalStatus as _S

            request.status = _S.PROCESSING
            request.save(update_fields=["status", "updated_at"])
            workflow.record_action(
                request=request,
                action=ApprovalAction.ACTION_MARK_PROCESSING,
                from_status=ApprovalStatus.APPROVED,
                to_status=ApprovalStatus.PROCESSING,
                actor=None,
                actor_type=ApprovalAction.ACTOR_SYSTEM,
                reason="Snippe payout initiated after approval.",
            )
        _notify(withdrawal.member, "Withdrawal in progress",
                f"Your payout of {withdrawal.amount} is being processed.", "withdrawal")
    else:
        workflow.record_action(
            request=request,
            action=ApprovalAction.ACTION_COMPLETE,
            from_status=ApprovalStatus.PENDING,
            to_status=ApprovalStatus.APPROVED,
            actor=None,
            actor_type=ApprovalAction.ACTOR_SYSTEM,
            reason="Approved; below Snippe payout minimum (officer handling).",
        )
        _notify(withdrawal.member, "Withdrawal approved",
                f"Your withdrawal of {withdrawal.amount} has been approved.", "withdrawal")


def _complete_rejected(withdrawal, request):
    if withdrawal.status in (WithdrawalRequest.Status.SUCCESS, WithdrawalRequest.Status.FAILED, WithdrawalRequest.Status.CANCELLED):
        return
    withdrawal.status = WithdrawalRequest.Status.REJECTED
    withdrawal.decline_reason = request.decision_reason or request.metadata.get("code", "")
    withdrawal.processed_at = timezone.now()
    withdrawal.save(update_fields=["status", "decline_reason", "processed_at"])
    _notify(withdrawal.member, "Withdrawal rejected", request.decision_reason or "Request rejected.", "withdrawal")


def _complete_cancelled(withdrawal, request):
    if withdrawal.status in (WithdrawalRequest.Status.SUCCESS, WithdrawalRequest.Status.FAILED):
        return
    withdrawal.status = WithdrawalRequest.Status.CANCELLED
    withdrawal.decline_reason = "Cancelled."
    withdrawal.save(update_fields=["status", "decline_reason"])
    _notify(withdrawal.member, "Withdrawal cancelled", "Your withdrawal request was cancelled.", "withdrawal")


# ---------------------------------------------------------------------------
# Webhook sync
# ---------------------------------------------------------------------------

def sync_withdrawal_outcome(withdrawal) -> ApprovalRequest | None:
    """Reflect a payout webhook outcome on the governance request.

    Called (once, after idempotency guards) from the payout webhook handler so
    the approval record follows the money. Never rolls back the financial
    transaction — best-effort by design."""
    request = request_for(withdrawal)
    if request is None:
        return None
    status = withdrawal.status
    if status == WithdrawalRequest.Status.SUCCESS and request.status != ApprovalStatus.COMPLETED:
        if request.status == ApprovalStatus.PROCESSING:
            workflow.complete(request, reason="Payout confirmed.")
        elif request.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED):
            request.status = ApprovalStatus.PROCESSING
            request.save(update_fields=["status", "updated_at"])
            workflow.complete(request, reason="Payout confirmed.")
    elif status == WithdrawalRequest.Status.FAILED and request.status not in (
        ApprovalStatus.COMPLETED,
        ApprovalStatus.FAILED,
    ):
        workflow.fail(request, reason=withdrawal.decline_reason or "Payout failed.")
    return request


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _notify(member, title, body, kind):
    from users.notifications import notify_user

    member_user = getattr(member, "user", None)
    if member_user is None:
        return
    try:
        notify_user(
            member_user,
            title,
            body,
            kind=kind,
            link="/wallet",
            sms_to=getattr(member, "phone_number", None) or None,
        )
    except Exception:  # noqa: BLE001 — notifications must never break money movement.
        logger.warning("failed to notify member %s", member.pk)


def _notify_officers(group, approval):
    if group is None:
        return
    from groups.models import GroupMembership
    from users.notifications import notify_user

    officers = (
        GroupMembership.objects.filter(
            group=group,
            is_active=True,
            role__in=workflow.COMMITTEE_ROLES,
        )
        .select_related("member__user")
    )
    for membership in officers:
        officer_user = membership.member.user
        if officer_user is None:
            continue
        try:
            notify_user(
                officer_user,
                "Withdrawal needs approval",
                f"A {approval.amount} withdrawal in {group.name} is waiting for review.",
                kind="withdrawal",
                link="/approvals",
            )
        except Exception:  # noqa: BLE001
            logger.warning("failed to notify officer %s", officer_user.pk)