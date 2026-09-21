"""Domain orchestration for Snippe collections & disbursements.

Success is NEVER taken from the initiation response — a payment is only "money
received" after a verified payment.completed webhook (or a reconciliation pull
of the same reference). Every handler below is idempotent and runs inside a
transaction (see STEP rules).
"""
import hashlib
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from accounts.models import (
    MemberSubscription,
    SavingsAccount,
    SavingsTransaction,
    WithdrawalRequest,
)
from accounts.services import post_savings_transaction
from groups.models import GroupContribution, VikobaGroup
from loans.models import LoanAccount, LoanSchedule
from members.models import Member

from ..errors import PaymentError, is_provider_timeout
from ..models import PaymentTransaction, ReconciliationRecord, WebhookEvent
from ..services.snippe import (
    PAYMENT_PREFIX,
    SnippeError,
    SnippeProvider,
)

logger = logging.getLogger("payments")

ZERO = Decimal("0.00")

# Snippe settles in integer TZS shillings, while some of our computed amounts
# (e.g. installment totals) carry cents. A tiny tolerance keeps those real
# roundings flowing instead of flagging the whole community; anything beyond it
# is a genuine mismatch that must go to reconciliation — never silently fixed.
MAX_AMOUNT_DISCREPANCY = Decimal("2.00")


def _customer_payload(member: Member, **extra) -> dict:
    return {
        "firstname": member.first_name or member.salutation,
        "lastname": member.last_name or "",
        "email": member.email or "",
        "phone": member.phone_number or "",
        **extra,
    }


def _idempotency_key(prefix: str, internal_reference: str) -> str:
    """Stable, <=30-char key derived from our immutable internal reference.
    Reusing the same internal reference on a retry yields the same key, which is
    what makes duplicate submissions collapse into one Snippe payment."""
    digest = hashlib.sha256(internal_reference.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}{digest}"


def _new_internal_reference() -> str:
    return PaymentTransaction._meta.get_field("internal_reference").default()


def _payment_key(internal_reference: str) -> str:
    return _idempotency_key(PAYMENT_PREFIX, internal_reference)


def _member_primary_account(member: Member) -> SavingsAccount:
    account = (
        SavingsAccount.objects.filter(member=member)
        .select_related("product")
        .first()
    )
    if account is None:
        raise ValueError("Member has no savings account to receive these funds.")
    return account


# ---------------------------------------------------------------------------
# Initiations (create a PaymentTransaction + fire the gateway request). These
# never mark money in — only status === webhook handlers do.
# ---------------------------------------------------------------------------

def initiate_savings_deposit(*, member: Member, amount: Decimal, phone: str = ""):
    """A member tops up their own savings account via Snippe mobile money.

    The account is auto-credited ONLY when the payment.completed webhook lands
    (handle_payment_completed, DEPOSIT branch) — never by this initiation.
    """
    if amount <= ZERO:
        raise ValueError("Deposit amount must be positive.")
    # Ensure the member actually has a savings account to receive the funds.
    _member_primary_account(member)
    if not phone:
        phone = member.phone_number

    with transaction.atomic():
        internal_ref = _new_internal_reference()
        tx = PaymentTransaction.objects.create(
            internal_reference=internal_ref,
            member=member,
            transaction_type=PaymentTransaction.Type.DEPOSIT,
            amount=amount,
            currency=member.preferred_currency or "TZS",
            phone=phone,
            idempotency_key=_payment_key(internal_ref),
            metadata={"purpose": "savings_deposit"},
        )

    provider = SnippeProvider()
    try:
        response = provider.create_payment(
            amount=amount,
            phone=phone,
            customer=_customer_payload(member),
            metadata={
                "internal_reference": tx.internal_reference,
                "purpose": "savings_deposit",
            },
            reference=_payment_key(tx.internal_reference),
        )
    except SnippeError as exc:
        if is_provider_timeout(exc):
            # Outcome unknown — the payment facts are indefinite (PENDING), so a
            # retry or reconciliation pull never double-charges the member.
            logger.warning("deposit initiation timed out; payment %s stays PENDING", tx.internal_reference)
            tx.save(update_fields=["updated_at"])
            raise PaymentError(
                code=PaymentError.PROVIDER_TIMEOUT,
                message="We could not confirm your payment with the provider. It is still pending — check again shortly.",
            ) from exc
        tx.apply_provider_status("failed", failure_reason=f"provider error {exc.code}")
        raise PaymentError(
            code=PaymentError.PROVIDER_ERROR,
            message="The payment provider rejected this request. Please try again.",
        ) from exc

    provider_reference = response.get("reference") or response.get("id")
    tx.mark_pending(provider_reference=provider_reference)
    return tx


def initiate_contribution_payment(*, member: Member, group: VikobaGroup, amount: Decimal, month: str, phone: str = ""):
    """Create a PENDING contribution and ask Snippe to collect from the member."""
    if amount <= ZERO:
        raise ValueError("Contribution amount must be positive.")
    if not phone:
        phone = member.phone_number

    with transaction.atomic():
        contribution = GroupContribution.objects.create(
            group=group,
            member=member,
            amount=amount,
            month=month,
            reference="",
            status=GroupContribution.Status.PENDING,
        )
        internal_ref = _new_internal_reference()
        tx = PaymentTransaction.objects.create(
            internal_reference=internal_ref,
            member=member,
            group=group,
            transaction_type=PaymentTransaction.Type.CONTRIBUTION,
            amount=amount,
            currency=member.preferred_currency or "TZS",
            phone=phone,
            idempotency_key=_payment_key(internal_ref),
            contribution=contribution,
        )
        tx.metadata["group"] = str(group.pk)
        tx.metadata["month"] = month
        tx.save(update_fields=["metadata"])

    provider = SnippeProvider()
    try:
        response = provider.create_payment(
            amount=amount,
            phone=phone,
            customer=_customer_payload(member),
            metadata={
                "internal_reference": tx.internal_reference,
                "purpose": "contribution",
                "group": str(group.pk),
                "month": month,
            },
            reference=_payment_key(tx.internal_reference),
        )
    except SnippeError as exc:  # keep the pending tx for reconciliation/retry
        contribution.reference = f"PROVIDER ERROR: {exc.code}"
        contribution.save(update_fields=["reference"])
        if is_provider_timeout(exc):
            logger.warning("contribution initiation timed out; payment %s stays PENDING", tx.internal_reference)
            tx.save(update_fields=["updated_at"])
            raise PaymentError(
                code=PaymentError.PROVIDER_TIMEOUT,
                message="We could not confirm your contribution with the provider. It is still pending — check again shortly.",
            ) from exc
        raise PaymentError(
            code=PaymentError.PROVIDER_ERROR,
            message="The payment provider rejected this request. Please try again.",
        ) from exc

    provider_reference = response.get("reference") or response.get("id")
    tx.mark_pending(provider_reference=provider_reference)
    contribution.reference = tx.internal_reference
    contribution.save(update_fields=["reference"])
    return tx


def initiate_subscription_payment(*, member: Member, plan, phone: str = "", payment_method: str = "", full_name: str = "", email: str = ""):
    """Member pays for a plan subscription via Snippe mobile money.

    Creates a PENDING MemberSubscription + PaymentTransaction and fires the
    USSD push. The plan is only ever ACTIVATED when the verified
    ``payment.completed`` webhook lands (handle_payment_completed ->
    Subscription branch) — never by this initiation.
    """
    if not phone:
        phone = member.phone_number
    if plan.currency and plan.currency != "TZS":
        # Snippe only moves TZS today; a non-TZS plan has no gateway yet.
        raise ValueError("This plan is not available for mobile-money payment yet.")

    with transaction.atomic():
        # A member may only have one in-flight subscription for a plan: cancel
        # earlier pending attempts so a single checkout stays the source of truth.
        MemberSubscription.objects.filter(
            member=member, plan=plan, status=MemberSubscription.Status.PENDING
        ).update(status=MemberSubscription.Status.CANCELLED)

        subscription = MemberSubscription.objects.create(
            member=member,
            plan=plan,
            status=MemberSubscription.Status.PENDING,
        )
        internal_ref = _new_internal_reference()
        tx = PaymentTransaction.objects.create(
            internal_reference=internal_ref,
            member=member,
            transaction_type=PaymentTransaction.Type.SUBSCRIPTION,
            amount=plan.price,
            currency=plan.currency or "TZS",
            phone=phone,
            idempotency_key=_payment_key(internal_ref),
            subscription=subscription,
            metadata={
                "purpose": "subscription",
                "plan_id": str(plan.pk),
                "plan_name": plan.name,
                "payment_method": payment_method or "",
            },
        )
        subscription.payment = tx
        subscription.save(update_fields=["payment"])

    provider = SnippeProvider()
    try:
        response = provider.create_payment(
            amount=plan.price,
            phone=phone,
            customer=_customer_payload(member),
            metadata={
                "internal_reference": tx.internal_reference,
                "purpose": "subscription",
                "plan_id": str(plan.pk),
                "plan_name": plan.name,
            },
            reference=_payment_key(tx.internal_reference),
        )
    except SnippeError as exc:
        if is_provider_timeout(exc):
            logger.warning("subscription initiation timed out; payment %s stays PENDING", tx.internal_reference)
            tx.save(update_fields=["updated_at"])
            raise PaymentError(
                code=PaymentError.PROVIDER_TIMEOUT,
                message="We could not confirm your subscription payment with the provider. It is still pending — check again shortly.",
            ) from exc
        tx.apply_provider_status("failed", failure_reason=f"provider error {exc.code}")
        _fail_pending_subscription(tx)
        raise PaymentError(
            code=PaymentError.PROVIDER_ERROR,
            message="The payment provider rejected this request. Please try again.",
        ) from exc

    provider_reference = response.get("reference") or response.get("id")
    tx.mark_pending(provider_reference=provider_reference)
    return tx


def initiate_loan_repayment(*, member: Member, loan: LoanAccount, installment_number: int, phone: str = ""):
    """Member initiates a mobile-money repayment for one scheduled installment."""
    if not phone:
        phone = member.phone_number
    if loan.member_id != member.pk:
        raise ValueError("This loan does not belong to you.")
    if loan.status != LoanAccount.DISBURSED:
        raise ValueError("Loan is not active.")

    installment = LoanSchedule.objects.filter(loan=loan, installment_number=installment_number).first()
    if installment is None:
        raise ValueError("Invalid installment number.")
    if installment.is_paid:
        raise ValueError("This installment has already been paid.")

    with transaction.atomic():
        internal_ref = _new_internal_reference()
        tx = PaymentTransaction.objects.create(
            internal_reference=internal_ref,
            member=member,
            transaction_type=PaymentTransaction.Type.LOAN_REPAYMENT,
            amount=installment.total_due,
            currency=member.preferred_currency or "TZS",
            phone=phone,
            idempotency_key=_payment_key(internal_ref),
            loan=loan,
            installment_number=installment_number,
            metadata={"loan_number": loan.loan_number, "installment_number": installment_number},
        )

    provider = SnippeProvider()
    try:
        response = provider.create_payment(
            amount=installment.total_due,
            phone=phone,
            customer=_customer_payload(member),
            metadata={
                "internal_reference": tx.internal_reference,
                "purpose": "loan_repayment",
                "loan_number": loan.loan_number,
                "installment_number": installment_number,
            },
            reference=_payment_key(tx.internal_reference),
        )
    except SnippeError as exc:
        if is_provider_timeout(exc):
            logger.warning("loan repayment initiation timed out; payment %s stays PENDING", tx.internal_reference)
            tx.save(update_fields=["updated_at"])
            raise PaymentError(
                code=PaymentError.PROVIDER_TIMEOUT,
                message="We could not confirm your repayment with the provider. It is still pending — check again shortly.",
            ) from exc
        tx.apply_provider_status("failed", failure_reason=f"provider error {exc.code}")
        raise PaymentError(
            code=PaymentError.PROVIDER_ERROR,
            message="The payment provider rejected this request. Please try again.",
        ) from exc

    provider_reference = response.get("reference") or response.get("id")
    tx.mark_pending(provider_reference=provider_reference)
    return tx





# ---------------------------------------------------------------------------
# Webhook handlers — the ONLY places money becomes confirmed.
# ---------------------------------------------------------------------------

@transaction.atomic
def handle_payment_completed(webhook_event: WebhookEvent, data: dict) -> PaymentTransaction:
    """True-up a PaymentTransaction + its funded business object.

    Idempotent: applied changes branch on the PaymentTransaction status, so a
    duplicate event can never double-post a contribution or repay a loan twice.

    Golden rule (reliability): the provider-reported amount is FACTS, never a
    licence to rewrite our expected amount. A verified mismatch (beyond the
    tiny integer-shilling tolerance) raises RECONCILIATION_REQUIRED instead of
    silently changing history, so a human must resolve it.
    """
    reference = data.get("reference") or ""
    try:
        tx = PaymentTransaction.objects.select_for_update().get(provider_reference=reference)
    except PaymentTransaction.DoesNotExist:
        # Provider settled money we know nothing about — record it, acknowledge
        # the webhook, and let accounting resolve it with the provider.
        _record_unknown_provider(
            reference,
            event=webhook_event,
            issue_type=ReconciliationRecord.IssueType.UNKNOWN_PROVIDER_TRANSACTION,
            notes="payment.completed webhook referenced a payment we have no record of.",
        )
        logger.warning("payment.completed for unknown provider reference %s", reference)
        return None

    if tx.status in (PaymentTransaction.Status.SUCCESS, PaymentTransaction.Status.RECONCILIATION_REQUIRED):
        return tx  # already applied, or already under supervised review

    fee, gross, net, currency = _parse_provider_amounts(data)
    issue = _validate_provider_amount(expected=tx.amount, gross=gross, fee=fee, currency=currency, tx_currency=tx.currency)
    if issue:
        notes = (
            f"Expected {tx.amount} {tx.currency or 'TZS'}, provider reported "
            f"{gross} {currency or tx.currency or 'TZS'} (fees {fee})."
        )
        _flag_for_reconciliation(
            tx,
            event=webhook_event,
            issue=issue,
            gross=gross,
            currency=currency,
            actual_status="completed",
            notes=notes,
        )
        return tx

    tx.fee = fee
    tx.net_amount = net
    tx.metadata = {**tx.metadata, "webhook": {
        "id": webhook_event.event_id,
        "type": webhook_event.event_type,
        "settlement": data.get("settlement"),
        "channel": data.get("channel"),
    }}
    tx.status = PaymentTransaction.Status.SUCCESS

    tx.completed_at = timezone.now()
    tx.save(update_fields=["fee", "net_amount", "metadata", "status", "completed_at", "updated_at"])

    if tx.transaction_type == PaymentTransaction.Type.CONTRIBUTION:
        contribution = tx.contribution
        if contribution and contribution.status != GroupContribution.Status.CONFIRMED:
            contribution.status = GroupContribution.Status.CONFIRMED
            contribution.reference = contribution.reference or tx.internal_reference
            contribution.save(update_fields=["status", "reference"])
            _credit_member_ledger(
                tx=tx,
                narration=f"Contribution {contribution.month} - {contribution.group.name}",
            )
    elif tx.transaction_type == PaymentTransaction.Type.LOAN_REPAYMENT:
        _settle_loan_installment(tx, narration="Mobile-money loan repayment")
    elif tx.transaction_type == PaymentTransaction.Type.DEPOSIT:
        _credit_member_ledger(tx, narration="Wallet top-up via mobile money")
    elif tx.transaction_type == PaymentTransaction.Type.SUBSCRIPTION:
        _activate_subscription(tx)

    # Provider fees are a financial fact of the settlement: journal them once,
    # keyed to the immutable internal reference (idempotent across replays).
    _post_provider_fee_leg(tx, fee)

    return tx


@transaction.atomic
def handle_payment_failed(webhook_event: WebhookEvent, data: dict) -> PaymentTransaction:
    reference = data.get("reference") or ""
    try:
        tx = PaymentTransaction.objects.select_for_update().get(provider_reference=reference)
    except PaymentTransaction.DoesNotExist:
        _record_unknown_provider(
            reference,
            event=webhook_event,
            issue_type=ReconciliationRecord.IssueType.UNKNOWN_PROVIDER_TRANSACTION,
            notes="payment.failed webhook referenced a payment we have no record of.",
        )
        return None
    if tx.status == PaymentTransaction.Status.SUCCESS:
        return tx
    tx.status = PaymentTransaction.Status.FAILED
    tx.failure_reason = data.get("failure_reason") or data.get("message") or ""
    tx.save(update_fields=["status", "failure_reason", "updated_at"])
    _fail_pending_subscription(tx)
    if tx.transaction_type == PaymentTransaction.Type.CONTRIBUTION and tx.contribution:
        tx.contribution.status = GroupContribution.Status.REJECTED
        tx.contribution.save(update_fields=["status"])
    return tx


@transaction.atomic
def handle_payout_completed(webhook_event: WebhookEvent, data: dict) -> PaymentTransaction:
    reference = data.get("reference") or ""
    try:
        tx = PaymentTransaction.objects.select_for_update().get(provider_reference=reference)
    except PaymentTransaction.DoesNotExist:
        _record_unknown_provider(
            reference,
            event=webhook_event,
            issue_type=ReconciliationRecord.IssueType.UNKNOWN_PROVIDER_TRANSACTION,
            notes="payout.completed webhook referenced a payout we have no record of.",
        )
        return None
    if tx.status == PaymentTransaction.Status.SUCCESS:
        return tx

    fee, gross, net, currency = _parse_provider_amounts(data)
    issue = _validate_provider_amount(expected=tx.amount, gross=gross, fee=fee, currency=currency, tx_currency=tx.currency)
    if issue:
        notes = (
            f"Payout expected {tx.amount} {tx.currency or 'TZS'}, provider reported "
            f"{gross} {currency or tx.currency or 'TZS'} (fees {fee})."
        )
        _flag_for_reconciliation(
            tx,
            event=webhook_event,
            issue=issue,
            gross=gross,
            currency=currency,
            actual_status="completed",
            notes=notes,
        )
        return tx

    tx.status = PaymentTransaction.Status.SUCCESS
    tx.completed_at = timezone.now()
    tx.fee = fee
    tx.net_amount = net
    tx.metadata = {**tx.metadata, "webhook": {
        "id": webhook_event.event_id,
        "type": webhook_event.event_type,
        "payout": data,
    }}
    tx.save(update_fields=["status", "completed_at", "fee", "net_amount", "metadata", "updated_at"])

    if tx.transaction_type == PaymentTransaction.Type.WITHDRAWAL and tx.withdrawal:
        withdrawal = tx.withdrawal
        withdrawal.status = WithdrawalRequest.Status.SUCCESS
        withdrawal.processed_at = timezone.now()
        withdrawal.save(update_fields=["status", "processed_at"])
        _debit_member_ledger(tx=tx, narration=f"Withdrawal {withdrawal.reference}")
        _sync_governance(withdrawal)

    _post_provider_fee_leg(tx, fee)
    return tx


@transaction.atomic
def handle_payout_failed(webhook_event: WebhookEvent, data: dict) -> PaymentTransaction:
    reference = data.get("reference") or ""
    try:
        tx = PaymentTransaction.objects.select_for_update().get(provider_reference=reference)
    except PaymentTransaction.DoesNotExist:
        _record_unknown_provider(
            reference,
            event=webhook_event,
            issue_type=ReconciliationRecord.IssueType.UNKNOWN_PROVIDER_TRANSACTION,
            notes="payout.failed webhook referenced a payout we have no record of.",
        )
        return None
    if tx.status == PaymentTransaction.Status.SUCCESS:
        return tx
    tx.status = PaymentTransaction.Status.FAILED
    tx.failure_reason = data.get("failure_reason") or data.get("message") or ""
    tx.save(update_fields=["status", "failure_reason", "updated_at"])
    if tx.transaction_type == PaymentTransaction.Type.WITHDRAWAL and tx.withdrawal:
        # Money never actually left the member — nothing to release.
        tx.withdrawal.status = WithdrawalRequest.Status.FAILED
        tx.withdrawal.decline_reason = "Mobile-money payout failed"
        tx.withdrawal.save(update_fields=["status", "decline_reason"])
        _sync_governance(tx.withdrawal)
    return tx


def _sync_governance(withdrawal):
    """Best-effort reflection of a payout outcome onto the governance record.

    The financial transaction is the source of truth; this is a non-fatal
    post-step so a governance failure can never roll back confirmed money."""
    try:
        from governance.withdrawals import sync_withdrawal_outcome

        sync_withdrawal_outcome(withdrawal)
    except Exception:  # noqa: BLE001
        logger.exception("governance sync failed for withdrawal %s", getattr(withdrawal, "pk", None))


def _fail_pending_subscription(tx: PaymentTransaction):
    """Mark the linked subscription FAILED when its payment fails/expires/voids.

    A subscription is only ever activated by a confirmed success; everything
    else must leave it inactive.
    """
    subscription = tx.subscription
    if subscription is None or subscription.status != MemberSubscription.Status.PENDING:
        return
    subscription.status = MemberSubscription.Status.FAILED
    subscription.save(update_fields=["status", "updated_at"])


def _activate_subscription(tx: PaymentTransaction):
    """Confirm a paid plan subscription (called from the webhook success path).

    Sets the subscription ACTIVE with start + next-billing dates, keeps the
    member's selected_plan in sync, and cancels any other pending subscription
    attempts so a member never holds two in-flight plans.
    """
    subscription = tx.subscription
    if subscription is None:
        return
    if subscription.status == MemberSubscription.Status.ACTIVE and subscription.expires_at:
        return  # already applied (duplicate event)

    subscription.payment = tx
    subscription.activate()

    member = tx.member
    if member.selected_plan_id != subscription.plan_id:
        member.selected_plan = subscription.plan
        member.save(update_fields=["selected_plan", "updated_at"])
    MemberSubscription.objects.filter(
        member=member, status=MemberSubscription.Status.PENDING
    ).exclude(pk=subscription.pk).update(status=MemberSubscription.Status.CANCELLED)


# ---------------------------------------------------------------------------
# Ledger application helpers (inside the same atomic block as the handler).
# ---------------------------------------------------------------------------

def _credit_member_ledger(tx: PaymentTransaction, narration: str = ""):
    """Put received money on the member's ledger (savings). Only called from a
    confirmed-completed webhook path, never from an initiation."""
    from accounts.services import DuplicateSavingsPostError

    account = _member_primary_account(tx.member)
    try:
        post_savings_transaction(
            account=account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=tx.amount,
            user=_webhook_staff_user(tx),
            narration=narration or f"Mobile money credit {tx.internal_reference}",
            idempotency_key=f"pay-credit-{tx.internal_reference}",
            group=tx.group,
            payment_transaction=tx,
            finance_transaction_type=_finance_ledger_type(tx),
        )
    except DuplicateSavingsPostError:
        # A duplicate webhook delivery already posted this money — nothing to do.
        return


def _debit_member_ledger(tx: PaymentTransaction, narration: str = ""):
    from accounts.services import DuplicateSavingsPostError

    account = _member_primary_account(tx.member)
    try:
        post_savings_transaction(
            account=account,
            transaction_type=SavingsTransaction.WITHDRAWAL,
            amount=tx.amount,
            user=_webhook_staff_user(tx),
            narration=narration or f"Mobile money debit {tx.internal_reference}",
            idempotency_key=f"pay-debit-{tx.internal_reference}",
            group=tx.group,
            payment_transaction=tx,
        )
    except DuplicateSavingsPostError:
        return


def _finance_ledger_type(tx: PaymentTransaction) -> str:
    """The journal transaction type that best describes the money movement.

    A contribution paid via mobile money credits the member's savings but is
    semantically a CONTRIBUTION; a wallet top-up is a DEPOSIT. Both post the
    same balanced journal (clearing debit / member-savings credit), the type is
    a label so the ledger tells the truth about what happened.
    """
    from finance.models import FinancialTransaction

    if tx.transaction_type == PaymentTransaction.Type.CONTRIBUTION:
        return FinancialTransaction.TransactionType.CONTRIBUTION
    if tx.transaction_type == PaymentTransaction.Type.DEPOSIT:
        return FinancialTransaction.TransactionType.DEPOSIT
    return FinancialTransaction.TransactionType.ADJUSTMENT


def _webhook_staff_user(tx: PaymentTransaction):
    """Webhooks are unauthenticated: use each member's linked staff/system user
    so the ledger keeps a consistent performed_by FK. Falls back to the admin
    user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    member_user = tx.member.user if tx.member and tx.member.user_id else None
    if member_user is not None:
        return member_user
    system = User.objects.filter(is_superuser=True).first()
    if system is not None:
        return system
    created = User.objects.create(
        username="snippe-system",
        email="system@snippe.local",
        role=User.ADMIN,
        is_active=True,
        is_staff=True,
    )
    return created


# ---------------------------------------------------------------------------
# Amount verification & reconciliation helpers.
# ---------------------------------------------------------------------------

def _payload_money(raw):
    """Coerce a provider amount (dict/int/str) to Decimal safely."""
    if raw is None:
        return Decimal("0.00")
    if isinstance(raw, dict):
        raw = raw.get("value") or 0
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _parse_provider_amounts(data: dict):
    """Read fee/gross/net/currency from either amount-dict or flat payloads.

    Snippe send: {"amount": {"value", "currency", "fees", "net"}}; some legacy
    events send {"amount": 50000, "currency": "TZS"}. Both are handled.
    """
    amount = data.get("amount")
    if isinstance(amount, dict):
        fee = _payload_money(amount.get("fees", 0))
        gross = _payload_money(amount.get("value", 0))
        net = _payload_money(amount.get("net", gross))
        currency = str(
            amount.get("currency")
            or (data.get("settlement") or {}).get("currency")
            or data.get("currency")
            or ""
        )
    else:
        gross = _payload_money(amount)
        net = gross
        fee = _payload_money(data.get("fees", 0))
        currency = str((data.get("settlement") or {}).get("currency") or data.get("currency") or "")
    return fee, gross, net, currency


def _validate_provider_amount(*, expected, gross, fee, currency, tx_currency):
    """None when facts hold; else a ReconciliationRecord.IssueType value.

    - Amount differences beyond the integer-shilling tolerance are real
      mismatches (the provider lied vs our expectation) → AMOUNT_MISMATCH.
    - A completed event that carried NO amount facts at all cannot be
      confirmed → AMOUNT_MISMATCH (do not guess).
    - Wrong currency → CURRENCY_MISMATCH.
    """
    if gross == 0 and fee == 0:
        return ReconciliationRecord.IssueType.AMOUNT_MISMATCH
    if abs(gross - expected) > MAX_AMOUNT_DISCREPANCY:
        return ReconciliationRecord.IssueType.AMOUNT_MISMATCH
    if currency and currency.upper() != (tx_currency or "TZS").upper():
        return ReconciliationRecord.IssueType.CURRENCY_MISMATCH
    return None


def _payment_audit(payment, action, *, event=None, notes="", record=None):
    """Write a finance audit trail for a payment lifecycle event."""
    try:
        from finance.models import AuditEvent

        AuditEvent.objects.create(
            user=None,
            action=action,
            reference=payment.internal_reference,
            metadata={
                "provider": payment.provider,
                "provider_reference": payment.provider_reference,
                "payment_id": payment.pk,
                "event_id": (event.event_id if event else None),
                "notes": notes,
                "reconciliation_record": (record.pk if record else None),
            },
        )
    except Exception:  # audit must never break the money path
        logger.exception("failed to write audit for %s", action)


def _flag_for_reconciliation(payment, *, event, issue, gross, currency, actual_status="", notes=""):
    """Raise RECONCILIATION_REQUIRED: record the exception, audit it, and stop.

    Financial effects are NOT applied. Resolution is a staff action; payment
    history is never silently rewritten.
    """
    record, _ = ReconciliationRecord.objects.get_or_create(
        provider=payment.provider,
        provider_reference=payment.provider_reference or "",
        issue_type=issue,
        defaults={
            "payment": payment,
            "internal_reference": payment.internal_reference,
            "event_id": (event.event_id if event else "") or "",
            "expected_amount": payment.amount,
            "actual_amount": gross if gross != 0 else None,
            "expected_currency": payment.currency or "TZS",
            "actual_currency": currency or "",
            "expected_status": payment.status,
            "actual_status": actual_status,
            "notes": notes,
        },
    )
    _payment_audit(payment, f"payment.reconciliation.{issue.lower()}", event=event, notes=notes, record=record)
    payment.require_reconciliation(reason=notes)
    return record


def _record_unknown_provider(provider_reference, *, event, issue_type, notes=""):
    """Record an unlinked provider event (money moved but no internal record)."""
    record, created = ReconciliationRecord.objects.get_or_create(
        provider="snippe",
        provider_reference=provider_reference,
        issue_type=issue_type,
        defaults={
            "event_id": (event.event_id if event else "") or "",
            "actual_status": (event.event_type if event else ""),
            "notes": notes,
        },
    )
    if created:
        logger.warning("reconciliation record created: %s %s", issue_type, provider_reference)
    return record


def _post_provider_fee_leg(tx: PaymentTransaction, fee: Decimal):
    """Expense the provider fee the settlement incurred on our books.

    DEBIT 5001-PROVIDER_FEE / CREDIT 1100-CLEARING, keyed to the payment's
    immutable internal reference so replays can never double-post it. This is a
    financial truth journaled once when the payment completes.
    """
    from finance.models import FinancialTransaction
    from finance.services.accounts_catalog import get_org_account
    from finance.services.engine import post_transaction

    if fee is None or fee <= 0:
        return
    with transaction.atomic():
        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.PROVIDER_FEE,
            amount=fee,
            currency=tx.currency or "TZS",
            group=tx.group,
            member=tx.member,
            description=f"Provider fee for {tx.internal_reference}",
            idempotency_key=f"fee-{tx.internal_reference}",
            payment_transaction=tx,
            entries=[
                {
                    "account": get_org_account("5001-PROVIDER_FEE"),
                    "entry_type": "DEBIT",
                    "amount": fee,
                },
                {
                    "account": get_org_account("1100-CLEARING"),
                    "entry_type": "CREDIT",
                    "amount": fee,
                },
            ],
        )


def _settle_loan_installment(tx: PaymentTransaction, narration: str = ""):
    if not tx.loan or not tx.installment_number:
        logger.warning("Loan repayment tx %s has no loan/installment link", tx.internal_reference)
        return
    loan = tx.loan
    installment = LoanSchedule.objects.select_for_update().get(
        loan=loan, installment_number=tx.installment_number
    )
    if installment.is_paid:
        return

    from loans.repayments import post_repayment

    post_repayment(
        loan=loan,
        amount=tx.amount,
        user=None,
        reference=f"PAY-{tx.internal_reference}",
        narration=narration or f"Mobile money repayment for installment {tx.installment_number}",
        payment_transaction=tx,
        installment_number=tx.installment_number,
    )