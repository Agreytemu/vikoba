"""Financial integrity monitoring.

On-demand, read-only checks that answer "do the books still tie?" against the
single source of truth (the double-entry journal in :mod:`finance`). Each check
returns ``status`` (ok / warning / error), a count and a bounded sample list —
nothing is mutated and nothing is silently "fixed".

Checks implemented (mirrors the Phase 5 integrity scope):
1. unbalanced_journals          - a transaction whose DEBIT/CREDIT totals differ
                                  (or has legs on only one side).
2. transactions_without_entries - FinancialTransaction rows with no journal legs.
3. completed_payments_unposted  - successfully settled provider payments with no
                                  financial transaction / journal (e.g. the
                                  documented subscription gap).
4. savings_drift                - cached SavingsAccount.balance vs the ledger.
5. loan_drift                   - stored outstanding_principal vs the journal
                                  (disbursements minus principal repaid).
6. duplicate_provider_references- provider_reference values seen more than once.
7. provider_transaction_id_unset- provider-related journals that never recorded
                                  the provider key at FinancialTransaction level.
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import FinancialAccount, FinancialTransaction, JournalEntry
from finance.services.balances import savings_account_balance

ZERO = Decimal("0.00")


def _check(status, count, samples):
    return {"status": status, "count": count, "samples": samples[:20]}


def _unbalanced_journals():
    """Transactions whose journal legs do not balance."""
    rows = (
        JournalEntry.objects.values("transaction")
        .annotate(
            debits=Coalesce(Sum("amount", filter=Q(entry_type=JournalEntry.DEBIT)), ZERO),
            credits=Coalesce(Sum("amount", filter=Q(entry_type=JournalEntry.CREDIT)), ZERO),
            legs=Count("id"),
        )
        .order_by()
    )
    bad = [row for row in rows if row["debits"] != row["credits"]]
    samples = []
    for row in bad[:20]:
        tx = (
            FinancialTransaction.objects.only(
                "reference", "status", "transaction_type", "group_id"
            )
            .filter(pk=row["transaction"])
            .first()
        )
        samples.append(
            {
                "transaction_id": row["transaction"],
                "reference": getattr(tx, "reference", ""),
                "status": getattr(tx, "status", ""),
                "type": getattr(tx, "transaction_type", ""),
                "debits": str(row["debits"]),
                "credits": str(row["credits"]),
                "legs": row["legs"],
            }
        )
    status = "error" if bad else "ok"
    return _check(status, len(bad), samples)


def _transactions_without_entries():
    """Financial transactions posted with no journal legs at all."""
    with_entries = JournalEntry.objects.values_list("transaction_id", flat=True).distinct()
    rows = list(
        FinancialTransaction.objects.exclude(pk__in=with_entries).only(
            "reference", "status", "transaction_type"
        )[:20]
    )
    status = "error" if rows else "ok"
    return _check(
        status,
        FinancialTransaction.objects.exclude(pk__in=with_entries).count(),
        [
            {"reference": r.reference, "status": r.status, "type": r.transaction_type}
            for r in rows
        ],
    )


def _completed_payments_unposted():
    """Settled PaymentTransactions that never produced a ledger posting."""
    from payments.models import PaymentTransaction

    unposted = list(
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS).exclude(
            financial_transactions__isnull=False
        )
        .order_by("-created_at")
        .only("internal_reference", "provider_reference", "transaction_type", "amount")[:20]
    )
    return _check(
        "error" if unposted else "ok",
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS)
        .exclude(financial_transactions__isnull=False)
        .count(),
        [
            {
                "internal_reference": r.internal_reference,
                "provider_reference": r.provider_reference or "",
                "type": r.transaction_type,
                "amount": str(r.amount),
            }
            for r in unposted
        ],
    )


def _savings_drift(limit=500):
    """Cached savings balance vs the journal for active savings accounts."""
    from accounts.models import SavingsAccount

    drift = []
    qs = SavingsAccount.objects.filter(is_active=True).order_by("id")[:limit]
    for account in qs.iterator(chunk_size=200):
        cached = account.balance or ZERO
        ledger = savings_account_balance(account)
        if cached != ledger:
            drift.append(
                {
                    "account_number": account.account_number,
                    "member": account.member.membership_number,
                    "cached": str(cached),
                    "ledger": str(ledger),
                }
            )
    status = "error" if drift else "ok"
    return _check(status, len(drift), drift)


def _loan_drift(limit=1000):
    """Stored outstanding_principal vs the journal for each loan.

    expected_outstanding = sum(1300 debits) - sum(1300 credits) over the loan's
    journals (disbursement debits the receivable; repayments credit it).
    """
    from loans.models import LoanAccount

    drift = []
    qs = LoanAccount.objects.filter(status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED])
    for loan in qs.order_by("id")[:limit].iterator(chunk_size=200):
        legs = (
            JournalEntry.objects.filter(
                transaction__loan_id=loan.pk,
                account__account_number__in=["1300-LOAN_PRINCIPAL", "1100-CLEARING"],
            )
            .values("account__account_number")
            .annotate(
                debits=Coalesce(Sum("amount", filter=Q(entry_type=JournalEntry.DEBIT)), ZERO),
                credits=Coalesce(Sum("amount", filter=Q(entry_type=JournalEntry.CREDIT)), ZERO),
            )
        )
        receivable_debits = ZERO
        receivable_credits = ZERO
        for leg in legs:
            if leg["account__account_number"] == "1300-LOAN_PRINCIPAL":
                receivable_debits = leg["debits"]
                receivable_credits = leg["credits"]
        expected = receivable_debits - receivable_credits
        expected = expected.quantize(Decimal("0.01"))
        if expected != (loan.outstanding_principal or ZERO):
            drift.append(
                {
                    "loan_number": loan.loan_number,
                    "member": loan.member.membership_number,
                    "expected_outstanding": str(expected),
                    "stored_outstanding": str(loan.outstanding_principal),
                }
            )
    status = "error" if drift else "ok"
    return _check(status, len(drift), drift)


def _duplicate_provider_references():
    """Provider references seen more than once (unique=True should prevent it)."""
    from payments.models import PaymentTransaction

    dupes = list(
        PaymentTransaction.objects.filter(provider_reference__isnull=False)
        .values("provider_reference")
        .annotate(n=Count("id"))
        .filter(n__gt=1)[:20]
    )
    status = "error" if dupes else "ok"
    return _check(
        status,
        len(dupes),
        [{"provider_reference": d["provider_reference"], "count": d["n"]} for d in dupes],
    )


def _provider_transaction_id_unset():
    """Provider-originated journals without a provider key at journal level."""
    unset = (
        FinancialTransaction.objects.filter(provider_transaction_id__isnull=True)
        .exclude(provider="")
        .count()
    )
    status = "warning" if unset else "ok"
    return _check(
        status,
        unset,
        [{"note": "provider_transaction_id is never populated by the current codebase"}]
        if unset
        else [],
    )


def run_integrity_checks(*, savings_limit=500, loans_limit=1000) -> dict:
    """Run every integrity check and return a consistent report dict."""
    checks = {
        "unbalanced_journals": _unbalanced_journals(),
        "transactions_without_entries": _transactions_without_entries(),
        "completed_payments_unposted": _completed_payments_unposted(),
        "savings_drift": _savings_drift(savings_limit),
        "loan_drift": _loan_drift(loans_limit),
        "duplicate_provider_references": _duplicate_provider_references(),
        "provider_transaction_id_unset": _provider_transaction_id_unset(),
    }
    errors = [name for name, c in checks.items() if c["status"] == "error"]
    warnings = [name for name, c in checks.items() if c["status"] == "warning"]
    return {
        "ok": not errors,
        "run_at": timezone.now().isoformat(),
        "error_checks": errors,
        "warning_checks": warnings,
        "checks": checks,
    }


def run_financial_integrity_report() -> dict:
    """Alias used by views/tests; see :func:`run_integrity_checks`."""
    return run_integrity_checks()