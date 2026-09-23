"""Ledger-derived dashboard KPIs.

Golden rule: every headline must trace to the double-entry journal. Cached
columns on SavingsAccount/LoanAccount are never trusted. Balances per account
are recomputed as the sign-aware sum of that account's journal legs for the
whole ledger (liability credit-normal for member savings; asset debit-normal
for clearing and loan receivables).
"""
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncDate

from finance.models import FinancialAccount, FinancialTransaction, JournalEntry
from finance.services.balances import ZERO


def _account_key(account_number):
    account = FinancialAccount.objects.get(account_number=account_number)
    return account.pk


def _net_balance(account_ids, *, credit_normal=False):
    legs = JournalEntry.objects.filter(account_id__in=account_ids).aggregate(
        debits=Sum(
            "amount",
            filter=Q(entry_type=JournalEntry.DEBIT),
            default=ZERO,
        ),
        credits=Sum(
            "amount",
            filter=Q(entry_type=JournalEntry.CREDIT),
            default=ZERO,
        ),
    )
    debits = legs["debits"] or ZERO
    credits = legs["credits"] or ZERO
    if credit_normal:
        return (credits - debits).quantize(ZERO)
    return (debits - credits).quantize(ZERO)


def _credit_income(account_ids):
    return (
        JournalEntry.objects.filter(
            account_id__in=account_ids,
            entry_type=JournalEntry.CREDIT,
        ).aggregate(total=Sum("amount", default=ZERO))["total"]
        or ZERO
    ).quantize(ZERO)


def run_org_financial_dashboard():
    """Org-level KPIs reconstructed from the journal, plus integrity drift."""
    from finance.services.accounts_catalog import get_org_account

    member_savings = (
        FinancialAccount.objects.filter(
            member__isnull=False,
            account_type=FinancialAccount.AccountType.LIABILITY,
        ).values_list("pk", flat=True)
    )
    member_savings_ids = list(member_savings)

    today = date.today()
    from_date = today - timedelta(days=29)
    last_30 = (
        FinancialTransaction.objects.annotate(
            day=TruncDate(Coalesce("posted_at", "created_at"))
        ).filter(day__gte=from_date)
    )

    daily = list(
        last_30.values("day")
        .annotate(count=Count("id"), total=Sum("amount", default=ZERO))
        .order_by("day")
    )
    type_breakdown = list(
        last_30.values("transaction_type")
        .annotate(count=Count("id"), total=Sum("amount", default=ZERO))
        .order_by("-count")
    )

    integrity = None
    try:
        from finance.services.integrity import run_integrity_checks

        integrity = run_integrity_checks()
    except Exception:
        pass

    return {
        "statement": "org_dashboard",
        "currency": "TZS",
        "as_of": today.isoformat(),
        "totals": {
            "member_savings": str(_net_balance(member_savings_ids, credit_normal=True)),
            "clearing_balance": str(_net_balance([_account_key("1100-CLEARING")])),
            "loans_outstanding": str(_net_balance([_account_key("1300-LOAN_PRINCIPAL")])),
            "interest_income": str(_credit_income([_account_key("4001-INTEREST_INCOME")])),
            "penalty_income": str(_credit_income([_account_key("4002-PENALTY_INCOME")])),
        },
        "activity_last_30_days": {
            "transactions": last_30.count(),
            "daily": [
                {
                    "date": str(item["day"]),
                    "count": item["count"],
                    "total": str(item["total"].quantize(ZERO)),
                }
                for item in daily
            ],
            "by_type": [
                {
                    "transaction_type": item["transaction_type"],
                    "count": item["count"],
                    "total": str(item["total"].quantize(ZERO)),
                }
                for item in type_breakdown
            ],
        },
        "integrity": integrity,
    }


def run_member_financial_dashboard(member):
    """Member-scoped dashboard: savings totals from the journal + loan status."""
    from finance.services.statements import run_member_savings_statement

    savings = run_member_savings_statement(member)
    loans = (
        FinancialTransaction.objects.filter(
            member=member,
            transaction_type=FinancialTransaction.TransactionType.LOAN_DISBURSEMENT,
        ).aggregate(disbursed=Sum("amount", default=ZERO))["disbursed"]
        or ZERO
    ).quantize(ZERO)

    return {
        "statement": "member_dashboard",
        "currency": "TZS",
        "member": {
            "membership_number": member.membership_number,
            "full_name": f"{member.first_name} {member.last_name}".strip(),
        },
        "savings": {
            "accounts": savings["accounts"],
            "totals": savings["totals"],
        },
        "loans_total_disbursed": str(loans),
    }