from django.db import transaction
from decimal import Decimal
import uuid
from datetime import datetime

from .models import SavingsAccount, SavingsTransaction


class DuplicateSavingsPostError(Exception):
    """Raised when an idempotency key has already posted this savings event.

    Callers (e.g. webhook ledger helpers) treat it as "already done" and skip,
    so a duplicate delivery can never double-credit or double-debit the member.
    """

    def __str__(self):
        return "This financial event has already been posted."


def _finance_transaction_type(transaction_type: str) -> str:
    mapping = {
        SavingsTransaction.DEPOSIT: "DEPOSIT",
        SavingsTransaction.WITHDRAWAL: "WITHDRAWAL",
        SavingsTransaction.INTEREST: "INTEREST",
        SavingsTransaction.ADJUSTMENT: "ADJUSTMENT",
    }
    return mapping[transaction_type]


def _post_finance_leg(*, account, transaction_type, amount, delta, user, narration, group,
                      payment_transaction, idempotency_key, savings_transaction,
                      finance_transaction_type=None):
    """Post a balanced journal for the savings leg through the transaction engine.

    The member-savings liability account is the primary leg; the offset leg is
    the mobile-money clearing account (or interest expense for interest postings).
    """
    from finance.services.accounts_catalog import (
        get_or_create_member_savings_account,
        get_org_account,
    )
    from finance.services.engine import post_transaction

    savings = get_or_create_member_savings_account(account)
    clearing = get_org_account("1100-CLEARING")
    interest_expense = get_org_account("5004-INTEREST_EXPENSE")

    if transaction_type == SavingsTransaction.INTEREST:
        debit, credit = interest_expense, savings
    elif delta > 0:
        debit, credit = clearing, savings
    else:
        debit, credit = savings, clearing

    post_transaction(
        transaction_type=finance_transaction_type or _finance_transaction_type(transaction_type),
        amount=amount,
        currency="TZS",
        group=group,
        member=account.member,
        description=narration or "",
        idempotency_key=idempotency_key or f"sav-{savings_transaction.reference}",
        initiated_by=user,
        payment_transaction=payment_transaction,
        savings_transaction=savings_transaction,
        entries=[
            {"account": debit, "entry_type": "DEBIT", "amount": amount},
            {"account": credit, "entry_type": "CREDIT", "amount": amount},
        ],
    )


def post_savings_transaction(
    *,
    account: SavingsAccount,
    transaction_type: str,
    amount: Decimal,
    user,
    narration="",
    idempotency_key=None,
    group=None,
    payment_transaction=None,
    finance_transaction_type=None,
):
    """
    Post a transaction to a savings account with proper locking, validation and
    ledger integration.

    Every savings event ALSO posts a balanced double-entry journal through the
    transaction engine (``finance.services.engine``) inside the same database
    transaction, making the journal the authoritative financial record while the
    cached ``SavingsAccount.balance`` remains a fast projection for the UI.

    Args:
        account: The SavingsAccount to transact on
        transaction_type: Type of transaction (deposit, withdrawal, interest, adjustment)
        amount: Transaction amount (must be positive)
        user: User performing the transaction
        narration: Optional description of the transaction
        idempotency_key: Optional stable key; when already posted, raises
            ``DuplicateSavingsPostError`` and changes nothing.
        group: Optional group scope for the financial transaction.
        payment_transaction: Optional PaymentTransaction that funded this event.

    Returns:
        SavingsTransaction: The created transaction object

    Raises:
        ValueError: If validation fails
        DuplicateSavingsPostError: If ``idempotency_key`` was already posted
    """
    # Validate amount
    if amount <= 0:
        raise ValueError("Amount must be positive")

    # Validate transaction type
    valid_types = [choice[0] for choice in SavingsTransaction.TRANSACTION_TYPES]
    if transaction_type not in valid_types:
        raise ValueError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")

    with transaction.atomic():
        # Lock the account row to prevent race conditions
        locked_account = SavingsAccount.objects.select_for_update().get(pk=account.pk)

        # Idempotency defence: refuse to create a second savings event (and a
        # second journal) when the same key has already been posted.
        if idempotency_key:
            from finance.models import FinancialTransaction

            if FinancialTransaction.objects.filter(idempotency_key=idempotency_key).exists():
                raise DuplicateSavingsPostError()

        # Determine balance change
        if transaction_type == SavingsTransaction.WITHDRAWAL:
            if not locked_account.product.allows_withdrawals:
                raise ValueError("Withdrawals not allowed on this account")

            # Check minimum balance requirement
            if locked_account.balance < amount:
                raise ValueError("Insufficient balance")

            delta = -amount
        elif transaction_type == SavingsTransaction.DEPOSIT:
            delta = amount
        elif transaction_type == SavingsTransaction.INTEREST:
            delta = amount
        elif transaction_type == SavingsTransaction.ADJUSTMENT:
            # Adjustments can be positive or negative based on the amount sign in the caller
            delta = amount
        else:
            delta = amount

        # Generate unique reference using UUID and timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_ref = f"TXN-{timestamp}-{uuid.uuid4().hex[:8].upper()}"

        # Create transaction record
        txn = SavingsTransaction.objects.create(
            account=locked_account,
            transaction_type=transaction_type,
            amount=amount,
            reference=unique_ref,
            narration=narration,
            performed_by=user
        )

        # Update account balance (cached projection of the ledger truth)
        locked_account.balance += delta
        locked_account.save(update_fields=["balance"])

        # Post the balanced journal — if this fails, the whole block rolls back
        # so we never leave "transaction created but ledger missing".
        _post_finance_leg(
            account=locked_account,
            transaction_type=transaction_type,
            amount=amount,
            delta=delta,
            user=user,
            narration=narration,
            group=group,
            payment_transaction=payment_transaction,
            idempotency_key=idempotency_key,
            savings_transaction=txn,
            finance_transaction_type=finance_transaction_type,
        )

    return txn