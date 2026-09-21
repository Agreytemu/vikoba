"""Payout/withdrawal orchestration over Snippe.

Withdrawal lifecycle (spec):

    PENDING -> APPROVED -> SENT_TO_SNIPPE -> SUCCESS | FAILED

- PENDING: member asked; nothing has moved.
- APPROVED: approved (staff or, by default, the system itself — auto flow).
  No ledger debit yet — funds remain on the member balance until a payout
  actually completes.
- SENT_TO_SNIPPE: payout request accepted by the provider (soft-reserved).
- SUCCESS: payout.completed webhook -> debit the member ledger (money is out).
- FAILED: payout failed/voided -> nothing was ever debited, so the member keeps
  the funds by construction.

The ledger debit happens exactly once, in handle_payout_completed.
"""
import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import SavingsAccount, WithdrawalRequest
from payments.errors import PaymentError, is_provider_timeout
from payments.models import PaymentTransaction, WebhookEvent
from payments.services.snippe import MIN_PAYOUT, SnippeError, SnippeProvider

logger = logging.getLogger("payments")


def _system_user(member):
    """Ledger / request actor for system-automated money movement (auto flow).
    Falls back to the member's linked user, then the superuser, then a dedicated
    system user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    member_user = getattr(member, "user", None)
    if member_user is not None and member_user.pk is not None:
        return member_user
    system = User.objects.filter(is_superuser=True).first()
    if system is not None:
        return system
    return User.objects.create(
        username="snippe-system",
        email="system@snippe.local",
        role=User.ADMIN,
        is_active=True,
        is_staff=True,
    )


def auto_withdraw(*, member, account, amount, narration="", network="mpesa"):
    """Member-initiated withdrawal that the system approves itself.

    Validates the balance up front (no staff in the loop), creates the
    WithdrawalRequest already APPROVED and immediately dispatches the Snippe
    payout. The ledger debit only happens on the payout.completed webhook, so a
    failed payout can never take a member's money.

    The payout ALWAYS goes to the member's verified phone number — a client can
    never redirect a withdrawal to another mobile-money number. `network`
    selects which Snippe mobile-money network the payout settles on.
    """
    amount = Decimal(str(amount))
    if amount < MIN_PAYOUT:
        raise ValueError(f"Minimum payout is {MIN_PAYOUT} TZS.")
    from payments.utils.phone import SNIPPE_NETWORK_IDS, normalize_phone

    if network not in SNIPPE_NETWORK_IDS:
        raise ValueError("Unknown payout network.")
    phone = normalize_phone(getattr(member, "phone_number", ""))
    if not phone.strip():
        raise ValueError("Add a mobile money number to receive the payout.")
    if not member.is_verified:
        raise ValueError("Withdrawals require a verified account.")
    if not getattr(member, "phone_verified", False):
        raise ValueError("Verify your phone number before you can withdraw.")

    with db_transaction.atomic():
        acct = SavingsAccount.objects.select_for_update().get(pk=account.pk)
        if not acct.is_active:
            raise ValueError("Account is not active.")
        if not acct.product.allows_withdrawals:
            raise ValueError("Withdrawals are not allowed on this account.")
        if acct.balance < amount:
            raise ValueError("Insufficient balance.")

    withdrawal = WithdrawalRequest.objects.create(
        member=member,
        account=account,
        amount=amount,
        narration=narration,
        status=WithdrawalRequest.Status.APPROVED,
        processed_by=_system_user(member),
        processed_at=timezone.now(),
    )
    tx = initiate_withdrawal_payout(withdrawal=withdrawal, phone=phone, network=network)
    return withdrawal, tx


def initiate_withdrawal_payout(*, withdrawal: WithdrawalRequest, phone="", network="mpesa") -> PaymentTransaction:
    """Staff-triggered dispatch of an APPROVED withdrawal via Snippe.

    Creates a PaymentTransaction (WITHDRAWAL, PROCESSING) and moves the
    withdrawal to SENT_TO_SNIPPE. No money moves here. `phone` overrides the
    recipient mobile-money number (defaults to the member's profile number);
    `network` selects the Snippe mobile-money network for the payout.
    """
    if withdrawal.status != WithdrawalRequest.Status.APPROVED:
        raise ValueError("Only approved withdrawals can be dispatched.")

    member = withdrawal.member
    from payments.utils.phone import SNIPPE_NETWORK_IDS, normalize_phone

    if network not in SNIPPE_NETWORK_IDS:
        raise ValueError("Unknown payout network.")

    recipient_phone = normalize_phone(phone) or member.phone_number
    with db_transaction.atomic():
        tx = PaymentTransaction.objects.create(
            member=member,
            amount=withdrawal.amount,
            currency=member.preferred_currency or "TZS",
            phone=recipient_phone,
            transaction_type=PaymentTransaction.Type.WITHDRAWAL,
            status=PaymentTransaction.Status.PENDING,
            idempotency_key=_payout_key(withdrawal),
            withdrawal=withdrawal,
            metadata={
                "withdrawal_reference": withdrawal.reference,
                "network": network,
            },
        )

    provider = SnippeProvider()
    try:
        response = provider.create_payout(
            amount=withdrawal.amount,
            recipient_phone=recipient_phone,
            recipient_name=f"{member.first_name} {member.last_name}".strip(),
            narration=f"Withdrawal {withdrawal.reference}",
            network=network,
            metadata={**tx.metadata, "internal_reference": tx.internal_reference},
            reference=tx.idempotency_key,
        )
    except SnippeError as exc:
        if is_provider_timeout(exc):
            # Outcome unknown: the payout may or may not have been accepted.
            # Keep the payment PENDING (never FAILED) so a retry can't double
            # pay out, and keep the withdrawal APPROVED for staff to dispatch
            # again after verifying with the provider.
            logger.warning("payout dispatch timed out; payment %s stays PENDING", tx.internal_reference)
            raise PaymentError(
                code=PaymentError.PROVIDER_TIMEOUT,
                message="We could not confirm your payout with the provider. Nothing leaves your account until it is verified.",
            ) from exc
        tx.status = PaymentTransaction.Status.FAILED
        tx.failure_reason = f"provider error {exc.code}"
        tx.save(update_fields=["status", "failure_reason"])
        raise PaymentError(
            code=PaymentError.PROVIDER_ERROR,
            message="The provider rejected this payout. Please try again.",
        ) from exc

    provider_reference = response.get("reference") or response.get("id")
    tx.mark_pending(provider_reference=provider_reference)
    tx.status = PaymentTransaction.Status.PROCESSING
    tx.save(update_fields=["status"])
    withdrawal.status = WithdrawalRequest.Status.SENT_TO_SNIPPE
    withdrawal.save(update_fields=["status"])
    return tx


def _payout_key(withdrawal: WithdrawalRequest) -> str:
    """Payout idempotency key: global + stable for retries of the same withdrawal."""
    return f"PAYOUT-{withdrawal.pk}"[:30]