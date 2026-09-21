"""The single controlled transaction engine for the VICOBA ledger.

Every financial operation in the platform must pass through this module. It
owns:

- reference allocation (human-readable, unique, never reused)
- balanced double-entry journal validation (SUM DEBITS == SUM CREDITS)
- idempotency (same idempotency key / provider reference never double-posts)
- status lifecycle (with a strict transition matrix)
- safe reversal (original is preserved; a new, balanced transaction is posted)
- audit events (transaction created/posted/failed/reversed) in the same
  database transaction

Callers are expected to run inside ``transaction.atomic()``; the engine nests
as a savepoint so it is also safe standalone.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from finance.models import (
    AuditEvent,
    FinancialAccount,
    FinancialTransaction,
    JournalEntry,
    ReferenceCounter,
)
from finance.services.accounts_catalog import get_org_account

MONEY = Decimal("0.01")


class FinancialError(Exception):
    """Raised by the engine with a stable machine-readable ``code``."""

    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_TRANSACTION = "INVALID_TRANSACTION"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    TRANSACTION_NOT_FOUND = "TRANSACTION_NOT_FOUND"
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    UNBALANCED_JOURNAL = "UNBALANCED_JOURNAL"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    ZERO_AMOUNT = "ZERO_AMOUNT"
    NEGATIVE_AMOUNT = "NEGATIVE_AMOUNT"
    INVALID_ENTRY = "INVALID_ENTRY"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    ALREADY_REVERSED = "ALREADY_REVERSED"
    REFERENCE_ALLOCATION_FAILED = "REFERENCE_ALLOCATION_FAILED"

    def __init__(self, *, code, message=""):
        message = message or code
        super().__init__(message)
        self.code = code
        self.message = message


PREFIX_BY_TYPE = {
    FinancialTransaction.TransactionType.CONTRIBUTION: "CON",
    FinancialTransaction.TransactionType.DEPOSIT: "DEP",
    FinancialTransaction.TransactionType.WITHDRAWAL: "WD",
    FinancialTransaction.TransactionType.LOAN_DISBURSEMENT: "LOAN",
    FinancialTransaction.TransactionType.LOAN_REPAYMENT: "REP",
    FinancialTransaction.TransactionType.INTEREST: "INT",
    FinancialTransaction.TransactionType.PENALTY: "PEN",
    FinancialTransaction.TransactionType.REFUND: "REF",
    FinancialTransaction.TransactionType.TRANSFER: "TFR",
    FinancialTransaction.TransactionType.GROUP_EXPENSE: "EXP",
    FinancialTransaction.TransactionType.MEMBERSHIP_FEE: "FEE",
    FinancialTransaction.TransactionType.PLATFORM_FEE: "PF",
    FinancialTransaction.TransactionType.PROVIDER_FEE: "PFEE",
    FinancialTransaction.TransactionType.SUBSCRIPTION: "SUB",
    FinancialTransaction.TransactionType.ADJUSTMENT: "ADJ",
    FinancialTransaction.TransactionType.REVERSAL: "RV",
}

# status x -> allowed next statuses
ALLOWED_TRANSITIONS = {
    FinancialTransaction.Status.INITIATED: {
        FinancialTransaction.Status.PENDING,
        FinancialTransaction.Status.PROCESSING,
        FinancialTransaction.Status.SUCCESS,
        FinancialTransaction.Status.FAILED,
        FinancialTransaction.Status.CANCELLED,
    },
    FinancialTransaction.Status.PENDING: {
        FinancialTransaction.Status.PROCESSING,
        FinancialTransaction.Status.SUCCESS,
        FinancialTransaction.Status.FAILED,
        FinancialTransaction.Status.CANCELLED,
    },
    FinancialTransaction.Status.PROCESSING: {
        FinancialTransaction.Status.SUCCESS,
        FinancialTransaction.Status.FAILED,
    },
    FinancialTransaction.Status.RECONCILIATION_REQUIRED: {
        FinancialTransaction.Status.SUCCESS,
        FinancialTransaction.Status.FAILED,
        FinancialTransaction.Status.REVERSED,
    },
    FinancialTransaction.Status.SUCCESS: {
        FinancialTransaction.Status.REFUNDED,
    },
}

REFERENCE_REUSE_MESSAGE = "This request has already been processed (duplicate financial transaction)."


def _money(value):
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise FinancialError(code=FinancialError.INVALID_TRANSACTION, message="Amount is not a valid decimal.")


def allocate_reference(transaction_type: str) -> str:
    """Allocate a stable reference like ``DEP-20260920-000123`` in its own
    atomic block so concurrent callers can never receive the same number."""
    prefix = PREFIX_BY_TYPE.get(transaction_type, "FIN")
    day = timezone.now().strftime("%Y%m%d")
    for _ in range(4):
        try:
            with transaction.atomic():
                counter, _ = ReferenceCounter.objects.select_for_update().get_or_create(
                    prefix=prefix, day=day, defaults={"last_sequence": 0}
                )
                counter.last_sequence += 1
                counter.save(update_fields=["last_sequence"])
                return f"{prefix}-{day}-{counter.last_sequence:06d}"
        except IntegrityError:
            continue
    raise FinancialError(
        code=FinancialError.REFERENCE_ALLOCATION_FAILED,
        message="Could not allocate a unique financial reference.",
    )


def _parse_entry(spec, default_currency):
    if not isinstance(spec, dict):
        raise FinancialError(code=FinancialError.INVALID_ENTRY, message="Journal entry must be a dict.")
    raw_account = spec.get("account")
    entry_type = str(spec.get("entry_type") or "").upper()
    amount = spec.get("amount")

    if entry_type not in (JournalEntry.DEBIT, JournalEntry.CREDIT):
        raise FinancialError(code=FinancialError.INVALID_ENTRY, message=f"Invalid entry type: {entry_type!r}.")
    if raw_account is None:
        raise FinancialError(code=FinancialError.ACCOUNT_NOT_FOUND, message="Journal entry has no account.")

    if isinstance(raw_account, FinancialAccount):
        account = raw_account
    elif isinstance(raw_account, str):
        account = get_org_account(raw_account)
    else:
        raise FinancialError(code=FinancialError.ACCOUNT_NOT_FOUND, message="Unknown account reference.")

    amount = _money(amount)
    if amount < 0:
        raise FinancialError(code=FinancialError.NEGATIVE_AMOUNT, message="Journal amounts must be positive.")
    if amount == 0:
        raise FinancialError(code=FinancialError.ZERO_AMOUNT, message="Journal amounts must be greater than zero.")

    currency = str(spec.get("currency") or default_currency or "TZS").upper()
    if currency != str(default_currency or "TZS").upper():
        raise FinancialError(code=FinancialError.CURRENCY_MISMATCH, message=f"Entry currency {currency} conflicts with transaction currency.")

    return {
        "account": account,
        "entry_type": entry_type,
        "amount": amount,
        "currency": currency,
        "description": str(spec.get("description") or "")[:255],
    }


def _find_by_idempotency(idempotency_key=None, provider_transaction_id=None, reference=None):
    query = FinancialTransaction.objects.none()
    if idempotency_key:
        query = FinancialTransaction.objects.filter(idempotency_key=idempotency_key)
    elif provider_transaction_id:
        query = FinancialTransaction.objects.filter(provider_transaction_id=provider_transaction_id)
    elif reference:
        query = FinancialTransaction.objects.filter(reference=reference)
    return query.order_by("-created_at").first()


def _audit(action, *, reference="", fin_tx=None, actor=None, ip=None, **metadata):
    AuditEvent.objects.create(
        user=actor,
        action=action,
        reference=reference or (fin_tx.reference if fin_tx else ""),
        transaction=fin_tx,
        metadata=metadata,
        ip_address=ip,
    )


def post_transaction(
    *,
    transaction_type,
    amount,
    entries,
    currency="TZS",
    group=None,
    member=None,
    description="",
    reference=None,
    provider="",
    provider_transaction_id=None,
    external_reference="",
    idempotency_key=None,
    initiated_by=None,
    payment_transaction=None,
    savings_transaction=None,
    deposit_request=None,
    withdrawal_request=None,
    contribution=None,
    loan=None,
    status=None,
    audit_ip=None,
):
    """Create and post ONE balanced financial transaction (atomic).

    ``entries`` is a list of ``{"account", "entry_type", "amount", ...}``. The
    journal is validated before anything is written and never leaves an
    unbalanced state. If ``idempotency_key`` / ``provider_transaction_id``
    already exist, the existing transaction is returned and nothing is posted a
    second time.

    Returns ``(FinancialTransaction, created: bool)``.
    """
    amount = _money(amount)
    if amount < 0:
        raise FinancialError(code=FinancialError.NEGATIVE_AMOUNT, message="Transaction amount must be positive.")
    if amount == 0:
        raise FinancialError(code=FinancialError.ZERO_AMOUNT, message="Transaction amount must be greater than zero.")

    with transaction.atomic():
        existing = _find_by_idempotency(
            idempotency_key=idempotency_key,
            provider_transaction_id=provider_transaction_id,
            reference=reference,
        )
        if existing is not None:
            return existing, False

        parsed = []
        for spec in entries:
            parsed.append(_parse_entry(spec, default_currency=currency))

        debit_sum = sum(e["amount"] for e in parsed if e["entry_type"] == JournalEntry.DEBIT)
        credit_sum = sum(e["amount"] for e in parsed if e["entry_type"] == JournalEntry.CREDIT)
        if not parsed:
            raise FinancialError(code=FinancialError.UNBALANCED_JOURNAL, message="A journal needs at least one entry.")
        if not any(e["entry_type"] == JournalEntry.DEBIT for e in parsed):
            raise FinancialError(code=FinancialError.UNBALANCED_JOURNAL, message="A journal needs at least one debit.")
        if not any(e["entry_type"] == JournalEntry.CREDIT for e in parsed):
            raise FinancialError(code=FinancialError.UNBALANCED_JOURNAL, message="A journal needs at least one credit.")
        if debit_sum != credit_sum:
            raise FinancialError(
                code=FinancialError.UNBALANCED_JOURNAL,
                message=f"Journal does not balance: debits {debit_sum} != credits {credit_sum}.",
            )

        if not reference:
            reference = allocate_reference(transaction_type)
        if FinancialTransaction.objects.filter(reference=reference).exists():
            raise FinancialError(code=FinancialError.DUPLICATE_TRANSACTION, message="Transaction reference already exists.")

        final_status = status or FinancialTransaction.Status.SUCCESS
        if final_status not in FinancialTransaction.Status.values:
            raise FinancialError(code=FinancialError.INVALID_STATUS_TRANSITION, message=f"Unknown status {final_status}.")

        tx = FinancialTransaction.objects.create(
            reference=reference,
            transaction_type=transaction_type,
            group=group,
            member=member,
            amount=amount,
            currency=str(currency or "TZS").upper(),
            status=final_status,
            description=description[:255],
            external_reference=external_reference[:120],
            provider=provider[:30],
            provider_transaction_id=provider_transaction_id,
            idempotency_key=idempotency_key,
            initiated_by=initiated_by,
            payment_transaction=payment_transaction,
            savings_transaction=savings_transaction,
            deposit_request=deposit_request,
            withdrawal_request=withdrawal_request,
            contribution=contribution,
            loan=loan,
            posted_at=timezone.now() if final_status == FinancialTransaction.Status.SUCCESS else None,
        )
        JournalEntry.objects.bulk_create(
            [
                JournalEntry(
                    transaction=tx,
                    account=e["account"],
                    entry_type=e["entry_type"],
                    amount=e["amount"],
                    currency=e["currency"],
                    description=e["description"],
                    position=index,
                )
                for index, e in enumerate(parsed)
            ]
        )

        _audit(
            AuditEvent.ACTION_TRANSACTION_CREATED,
            fin_tx=tx,
            actor=initiated_by,
            ip=audit_ip,
            amount=str(amount),
            currency=tx.currency,
        )
        if final_status == FinancialTransaction.Status.SUCCESS:
            _audit(
                AuditEvent.ACTION_TRANSACTION_POSTED,
                fin_tx=tx,
                actor=initiated_by,
                ip=audit_ip,
            )
        elif final_status == FinancialTransaction.Status.FAILED:
            _audit(
                AuditEvent.ACTION_TRANSACTION_FAILED,
                fin_tx=tx,
                actor=initiated_by,
                ip=audit_ip,
            )
        return tx, True


def mark_status(
    tx: FinancialTransaction,
    new_status: str,
    *,
    reason="",
    actor=None,
    audit_ip=None,
):
    """Transition a transaction through its lifecycle using the whitelist."""
    with transaction.atomic():
        locked = FinancialTransaction.objects.select_for_update().get(pk=tx.pk)
        if str(new_status) == locked.status:
            return locked

        allowed = ALLOWED_TRANSITIONS.get(locked.status, set())
        if new_status not in allowed:
            raise FinancialError(
                code=FinancialError.INVALID_STATUS_TRANSITION,
                message=f"Cannot move {locked.status} -> {new_status}.",
            )

        updates = {"status": new_status, "updated_at": timezone.now()}
        if new_status == FinancialTransaction.Status.SUCCESS:
            updates["posted_at"] = timezone.now()
        for field, value in updates.items():
            setattr(locked, field, value)
        locked.save(update_fields=list(updates.keys()))

        action = {
            FinancialTransaction.Status.SUCCESS: AuditEvent.ACTION_TRANSACTION_POSTED,
            FinancialTransaction.Status.FAILED: AuditEvent.ACTION_TRANSACTION_FAILED,
            FinancialTransaction.Status.CANCELLED: AuditEvent.ACTION_TRANSACTION_CANCELLED,
        }.get(new_status)
        if action:
            _audit(action, fin_tx=locked, actor=actor, ip=audit_ip, reason=reason)
        return locked


def get_transaction(reference: str) -> FinancialTransaction:
    try:
        return FinancialTransaction.objects.select_related(
            "group", "member", "initiated_by"
        ).prefetch_related("entries", "entries__account").get(reference=reference)
    except FinancialTransaction.DoesNotExist:
        raise FinancialError(code=FinancialError.TRANSACTION_NOT_FOUND, message=f"Transaction {reference} not found.")


def reverse_transaction(
    tx: FinancialTransaction,
    *,
    reason: str,
    initiated_by=None,
    audit_ip=None,
):
    """Safely undo a successful transaction.

    The original transaction is never deleted or edited: it is marked REVERSED
    and a new, balanced REVERSAL transaction (exactly opposite journal) is
    posted so the ledger remains balanced and the history stays intact.
    """
    reason = (reason or "Reversal").strip()
    with transaction.atomic():
        locked = (
            FinancialTransaction.objects.select_for_update()
            .select_related("group", "member")
            .get(pk=tx.pk)
        )
        if locked.status == FinancialTransaction.Status.REVERSED:
            raise FinancialError(code=FinancialError.ALREADY_REVERSED, message="Transaction is already reversed.")
        if locked.reversals.exists():
            raise FinancialError(code=FinancialError.ALREADY_REVERSED, message="Transaction already has a reversal.")
        if locked.status not in (
            FinancialTransaction.Status.SUCCESS,
            FinancialTransaction.Status.PENDING,
            FinancialTransaction.Status.RECONCILIATION_REQUIRED,
        ):
            raise FinancialError(
                code=FinancialError.INVALID_STATUS_TRANSITION,
                message=f"Cannot reverse a transaction in status {locked.status}.",
            )

        original_entries = list(locked.entries.select_related("account").order_by("position"))

        reversal_entries = [
            {
                "account": e.account,
                "entry_type": JournalEntry.CREDIT if e.entry_type == JournalEntry.DEBIT else JournalEntry.DEBIT,
                "amount": e.amount,
                "description": f"Reversal of {locked.reference}: {reason[:180]}",
            }
            for e in original_entries
        ]

        reversal, _ = post_transaction(
            transaction_type=FinancialTransaction.TransactionType.REVERSAL,
            amount=locked.amount,
            currency=locked.currency,
            group=locked.group,
            member=locked.member,
            description=f"Reversal of {locked.reference}",
            entries=reversal_entries,
            idempotency_key=f"REV-OF-{locked.reference}",
            initiated_by=initiated_by,
            status=FinancialTransaction.Status.SUCCESS,
            audit_ip=audit_ip,
        )

        locked.status = FinancialTransaction.Status.REVERSED
        locked.reversal_reason = reason
        locked.save(update_fields=["status", "reversal_reason", "updated_at"])

        reversal.reversal_of = locked
        reversal.reversal_reason = reason
        reversal.save(update_fields=["reversal_of", "reversal_reason"])

        _audit(
            AuditEvent.ACTION_TRANSACTION_REVERSED,
            fin_tx=locked,
            actor=initiated_by,
            ip=audit_ip,
            reversal_reference=reversal.reference,
            reason=reason,
        )
        _audit(
            AuditEvent.ACTION_TRANSACTION_REVERSED,
            fin_tx=reversal,
            actor=initiated_by,
            ip=audit_ip,
            original_reference=locked.reference,
            reason=reason,
        )
        return reversal


def ensure_balanced_journal(entries) -> None:
    """Lightweight validation helper used by tests and callers before posting."""
    debit_sum = sum(_money(e.get("amount")) for e in entries if e.get("entry_type") == JournalEntry.DEBIT)
    credit_sum = sum(_money(e.get("amount")) for e in entries if e.get("entry_type") == JournalEntry.CREDIT)
    if debit_sum != credit_sum:
        raise FinancialError(
            code=FinancialError.UNBALANCED_JOURNAL,
            message=f"Journal does not balance: debits {debit_sum} != credits {credit_sum}.",
        )