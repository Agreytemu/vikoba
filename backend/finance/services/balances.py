"""Authoritative, ledger-derived balance queries.

There is exactly ONE place balances live conceptually: the journal. Cached
fields such as ``SavingsAccount.balance`` remain as fast projections for the
existing UI but are derived and must reconcile with these queries. New balances
must be read from here, never computed ad-hoc in components/controllers.
"""
from decimal import Decimal

from django.db.models import Q, Sum

from finance.models import FinancialAccount, JournalEntry
from finance.services.accounts_catalog import get_or_create_member_savings_account

ZERO = Decimal("0.00")


def account_balance(account: FinancialAccount) -> Decimal:
    """Signed balance of one account from its journal.

    A credit-normal account (liability/equity/income) is the net credit minus
    debit; a debit-normal account (asset/expense) is the net debit minus credit.
    """
    totals = JournalEntry.objects.filter(account=account).aggregate(
        debits=Sum("amount", filter=Q(entry_type=JournalEntry.DEBIT)),
        credits=Sum("amount", filter=Q(entry_type=JournalEntry.CREDIT)),
    )
    debits = totals["debits"] or ZERO
    credits = totals["credits"] or ZERO
    if account.is_liability_or_equity_or_income:
        return credits - debits
    return debits - credits


def account_balance_by_number(account_number: str) -> Decimal:
    try:
        account = FinancialAccount.objects.get(account_number=account_number)
    except FinancialAccount.DoesNotExist:
        from finance.services.engine import FinancialError

        raise FinancialError(code=FinancialError.ACCOUNT_NOT_FOUND, message=f"Account {account_number} not found.")
    return account_balance(account)


def member_savings_balance(member) -> Decimal:
    """The member's total savings as recorded by the journal."""
    account_ids = list(
        FinancialAccount.objects.filter(
            member=member,
            savings_account__isnull=False,
            account_type=FinancialAccount.AccountType.LIABILITY,
        ).values_list("id", flat=True)
    )
    if not account_ids:
        return ZERO
    totals = JournalEntry.objects.filter(account_id__in=account_ids).aggregate(
        debits=Sum("amount", filter=Q(entry_type=JournalEntry.DEBIT)),
        credits=Sum("amount", filter=Q(entry_type=JournalEntry.CREDIT)),
    )
    return (totals["credits"] or ZERO) - (totals["debits"] or ZERO)


def savings_account_balance(savings_account) -> Decimal:
    """Ledger balance for one operational savings account.

    Creates the member savings financial account lazily (idempotent) so reading
    a balance is always consistent with posting one.
    """
    account = get_or_create_member_savings_account(savings_account)
    return account_balance(account)


def reconcile_savings_account(savings_account) -> dict:
    """Compare the cached ``SavingsAccount.balance`` with the journal truth.

    Returns ``{"cached": ..., "ledger": ..., "in_sync": bool}`` — used by tests
    and the ops dashboard to detect drift.
    """
    ledger = savings_account_balance(savings_account)
    cached = savings_account.balance or ZERO
    return {"cached": cached, "ledger": ledger, "in_sync": cached == ledger}