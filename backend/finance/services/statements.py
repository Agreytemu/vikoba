"""Ledger-derived member statements.

Golden rule (see the audit report): a reported figure is only trustworthy if it
traces to the double-entry journal. These builders read exclusively from
:mod:`finance.JournalEntry` / :mod:`finance.FinancialTransaction` — cached
projections are never trusted.

Two statements are produced:
- ``savings`` — a balanced, per-account statement with a true opening/closing
  balance and a running balance on every row (member savings is a credit-normal
  liability: a CREDIT increases the member's money, a DEBIT reduces it).
- ``financial`` — a chronological itemisation of every FinancialTransaction the
  member owns, each row carrying its journal legs so nothing is report-only.
"""
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import FinancialTransaction, JournalEntry
from finance.services.accounts_catalog import get_or_create_member_savings_account
from finance.services.balances import ZERO

DATE_FORMAT = "%Y-%m-%d"


class StatementError(ValueError):
    """Invalid statement request parameters."""


def _parse_period(start=None, end=None):
    """Convert 'YYYY-MM-DD' bounds to inclusive datetimes (both optional)."""
    start_at = None
    end_at = None
    if start:
        try:
            day = datetime.strptime(start, DATE_FORMAT)
            start_at = timezone.make_aware(datetime.combine(day.date(), time.min))
        except ValueError as exc:
            raise StatementError(f"Invalid start date {start!r}; expected YYYY-MM-DD.") from exc
    if end:
        try:
            day = datetime.strptime(end, DATE_FORMAT)
            end_at = timezone.make_aware(datetime.combine(day.date(), time.max))
        except ValueError as exc:
            raise StatementError(f"Invalid end date {end!r}; expected YYYY-MM-DD.") from exc
    return start_at, end_at


def _leg_rows(financial_account, start_at=None, end_at=None):
    """Chronological journal legs for one member-savings financial account."""
    qs = (
        JournalEntry.objects.filter(account=financial_account)
        .select_related("transaction")
        .annotate(posted_eff=Coalesce("transaction__posted_at", "transaction__created_at"))
    )
    if start_at:
        qs = qs.filter(posted_eff__gte=start_at)
    if end_at:
        qs = qs.filter(posted_eff__lte=end_at)
    return qs.order_by("posted_eff", "position")


def _signed_delta(entry_type, amount):
    """Member-money direction: CREDIT grows the member balance, DEBIT shrinks it."""
    if entry_type == JournalEntry.CREDIT:
        return amount
    return -amount


def _money(value):
    return (value or ZERO).quantize(ZERO)


def _member_summary(member):
    return {
        "membership_number": member.membership_number,
        "full_name": f"{member.first_name} {member.last_name}".strip(),
        "id": member.pk,
    }


def run_member_savings_statement(member, *, account=None, start=None, end=None):
    """Per-account savings statement with opening/closing + running balances."""
    from accounts.models import SavingsAccount

    start_at, end_at = _parse_period(start, end)
    accounts = [account] if account else list(
        SavingsAccount.objects.filter(member=member, is_active=True).order_by("id")
    )

    output_accounts = []
    totals = {"opening": ZERO, "closing": ZERO}
    for savings in accounts:
        financial = get_or_create_member_savings_account(savings)
        legs = _leg_rows(financial, start_at, end_at)

        opening = ZERO
        if start_at:
            open_legs = JournalEntry.objects.filter(account=financial).annotate(
                posted_eff=Coalesce("transaction__posted_at", "transaction__created_at")
            ).filter(posted_eff__lt=start_at)
            opening = sum(
                (_signed_delta(_leg.entry_type, _leg.amount) for _leg in open_legs),
                ZERO,
            )
        opening = _money(opening)

        rows = []
        running = opening
        for leg in legs:
            tx = leg.transaction
            running += _signed_delta(leg.entry_type, leg.amount)
            rows.append(
                {
                    "date": (tx.posted_at or tx.created_at).isoformat(),
                    "reference": tx.reference,
                    "status": tx.status,
                    "transaction_type": tx.transaction_type,
                    "description": tx.description,
                    "entry_type": leg.entry_type,
                    "amount": str(_money(abs(leg.amount))),
                    "delta": str(_signed_delta(leg.entry_type, leg.amount)),
                    "running_balance": str(_money(running)),
                }
            )

        closing = _money(running)
        totals["opening"] += opening
        totals["closing"] += closing
        output_accounts.append(
            {
                "account_number": savings.account_number,
                "product": savings.product.name if savings.product_id else "",
                "opening_balance": str(opening),
                "closing_balance": str(closing),
                "rows": rows,
            }
        )

    return {
        "statement": "savings",
        "member": _member_summary(member),
        "currency": "TZS",
        "period": {
            "start": start_at.isoformat() if start_at else None,
            "end": end_at.isoformat() if end_at else None,
        },
        "accounts": output_accounts,
        "totals": {"opening": str(totals["opening"]), "closing": str(totals["closing"])},
    }


def run_member_financial_activity(member, *, start=None, end=None):
    """Chronological itemisation of the member's ledged financial transactions."""
    start_at, end_at = _parse_period(start, end)
    qs = (
        FinancialTransaction.objects.filter(member=member)
        .select_related("group", "reversal_of")
        .prefetch_related("entries", "entries__account")
        .annotate(posted_eff=Coalesce("posted_at", "created_at"))
    )
    if start_at:
        qs = qs.filter(posted_eff__gte=start_at)
    if end_at:
        qs = qs.filter(posted_eff__lte=end_at)

    rows = []
    for tx in qs.order_by("posted_eff", "id"):
        rows.append(
            {
                "date": (tx.posted_at or tx.created_at).isoformat(),
                "reference": tx.reference,
                "transaction_type": tx.transaction_type,
                "status": tx.status,
                "amount": str(tx.amount),
                "currency": tx.currency,
                "description": tx.description,
                "reversed": bool(tx.reversal_of_id),
                "entries": [
                    {
                        "account": leg.account.account_number,
                        "entry_type": leg.entry_type,
                        "amount": str(leg.amount),
                    }
                    for leg in tx.entries.all()
                ],
            }
        )

    return {
        "statement": "financial",
        "member": _member_summary(member),
        "currency": "TZS",
        "period": {
            "start": start_at.isoformat() if start_at else None,
            "end": end_at.isoformat() if end_at else None,
        },
        "rows": rows,
        "count": len(rows),
    }


def run_member_statement(member, *, kind="savings", account=None, start=None, end=None):
    """Dispatch for the member statement endpoint."""
    if kind == "financial":
        return run_member_financial_activity(member, start=start, end=end)
    return run_member_savings_statement(member, account=account, start=start, end=end)


def run_group_savings_statement(group, *, start=None, end=None):
    """Group statement built from the journal (member-savings flows only).

    Every FinancialTransaction scoped to the group is listed. ``delta`` is the
    money that actually landed in / left members' savings (the sum, sign-aware,
    over the transaction's member-savings legs — a balanced journal nets to zero
    across ALL accounts, so only the member-liability legs move the running
    figure). Non-savings flows (disbursements, repayments, penalties, fees) are
    surfaced separately in ``flow_totals`` so nothing is report-only.
    """
    start_at, end_at = _parse_period(start, end)
    qs = (
        FinancialTransaction.objects.filter(group=group)
        .select_related("member")
        .annotate(posted_eff=Coalesce("posted_at", "created_at"))
    )
    if start_at:
        qs = qs.filter(posted_eff__gte=start_at)
    if end_at:
        qs = qs.filter(posted_eff__lte=end_at)

    rows = []
    flow_totals = {}
    opening = ZERO
    if start_at:
        open_tx = (
            FinancialTransaction.objects.filter(group=group)
            .annotate(posted_eff=Coalesce("posted_at", "created_at"))
            .filter(posted_eff__lt=start_at)
        )
        for tx in open_tx.prefetch_related("entries__account"):
            opening += _tx_member_delta(tx)
    opening = _money(opening)

    running = opening
    for tx in qs.prefetch_related("entries__account").order_by("posted_eff", "id"):
        delta = _tx_member_delta(tx)
        running += delta
        flow_totals[tx.transaction_type] = _money(
            (flow_totals.get(tx.transaction_type) or ZERO) + tx.amount
        )
        rows.append(
            {
                "date": (tx.posted_at or tx.created_at).isoformat(),
                "reference": tx.reference,
                "transaction_type": tx.transaction_type,
                "status": tx.status,
                "description": tx.description,
                "member": tx.member.membership_number if tx.member_id else "",
                "amount": str(tx.amount),
                "delta": str(delta),
                "running_balance": str(_money(running)),
            }
        )

    inflows = sum((r_delta for r_delta in (Decimal(row["delta"]) for row in rows) if r_delta > 0), ZERO)
    outflows = sum((-r_delta for r_delta in (Decimal(row["delta"]) for row in rows) if r_delta < 0), ZERO)
    return {
        "statement": "group_savings",
        "group": {"id": group.pk, "name": group.name, "area": group.area},
        "currency": "TZS",
        "period": {
            "start": start_at.isoformat() if start_at else None,
            "end": end_at.isoformat() if end_at else None,
        },
        "opening_balance": str(opening),
        "closing_balance": str(_money(running)),
        "summary": {
            "transactions": len(rows),
            "inflows": str(inflows),
            "outflows": str(outflows),
            "flow_totals": {k: str(v) for k, v in sorted(flow_totals.items())},
        },
        "rows": rows,
    }


def _tx_member_delta(tx: FinancialTransaction):
    """Sign-aware member-savings flow for one transaction.

    Member savings are credit-normal liabilities: a CREDIT on a member bound
    account increases the member's money, a DEBIT reduces it. Returns the net
    of those legs (zero for non-savings flows such as loan disbursement).
    """
    delta = ZERO
    for leg in tx.entries.select_related("account").all():
        if not leg.account.member_id:
            continue
        if leg.entry_type == JournalEntry.CREDIT:
            delta += leg.amount
        else:
            delta -= leg.amount
    return delta


def run_group_contribution_report(group, *, month=None, member=None):
    """Contribution report tying scheduled records to the journal.

    Scheduled rows come from the group's contribution record; the ``collected``
    half is derived from CONTRIBUTION journal legs (never from cached fields),
    so a confirmation without a ledger posting is visible as a gap rather than
    silently reported as collected. Any group member may read their own rows;
    leaders/staff see the whole group.
    """
    scheduled = group.contributions.select_related("member", "member__user").all()
    if month:
        scheduled = scheduled.filter(month=month)
    if member is not None:
        scheduled = scheduled.filter(member=member)

    scheduled_items = list(scheduled.order_by("month", "-created_at"))
    ids = [item.pk for item in scheduled_items]

    ledger = {
        tx.contribution_id: tx
        for tx in FinancialTransaction.objects.filter(contribution_id__in=ids or [None])
        .order_by("-posted_at", "-id")
        .select_related("member")
    } if ids else {}

    rows = []
    by_member = {}
    ledged_amount = ZERO
    for item in scheduled_items:
        tx = ledger.get(item.pk)
        status = item.status
        collected = bool(tx)
        if collected:
            ledged_amount += tx.amount
        rows.append(
            {
                "member": {
                    "membership_number": item.member.membership_number,
                    "full_name": f"{item.member.first_name} {item.member.last_name}".strip(),
                },
                "month": item.month,
                "amount": str(item.amount),
                "status": status,
                "reference": item.reference,
                "collected": collected,
                "ledger": (
                    {
                        "amount": str(tx.amount),
                        "date": (tx.posted_at or tx.created_at).isoformat(),
                        "reference": tx.reference,
                    }
                    if tx
                    else None
                ),
            }
        )
        bucket = by_member.setdefault(
            item.member.membership_number,
            {"count": 0, "amount": ZERO, "collected": 0, "collected_amount": ZERO},
        )
        bucket["count"] += 1
        bucket["amount"] += item.amount
        if collected:
            bucket["collected"] += 1
            bucket["collected_amount"] += tx.amount

    summary_counts = [i for i in scheduled_items if ledger.get(i.pk)]
    return {
        "statement": "group_contributions",
        "group": {"id": group.pk, "name": group.name},
        "currency": "TZS",
        "period": {"month": month},
        "summary": {
            "scheduled_count": len(scheduled_items),
            "scheduled_amount": str(
                sum((i.amount for i in scheduled_items), ZERO)
            ),
            "collected_count": len(summary_counts),
            "collected_amount": str(ledged_amount),
            "unrecorded_in_ledger": len(scheduled_items) - len(summary_counts),
        },
        "by_member": {
            k: {"count": v["count"], "amount": str(_money(v["amount"])),
                "collected": v["collected"],
                "collected_amount": str(_money(v["collected_amount"]))}
            for k, v in sorted(by_member.items())
        },
        "rows": rows,
    }


def _tx_loan_split(tx):
    """Principal/interest/penalty split of one loan-tied journal posting.

    Split by the org receivable accounts actually used by the loan engine:
    ``1300-LOAN_PRINCIPAL`` (disbursement DEBIT / repayment CREDIT),
    ``4001-INTEREST_INCOME`` (repayment CREDIT), ``1310-LOAN_INTEREST``
    (penalty paid via repayment), ``4002-PENALTY_INCOME`` (penalty charge).
    """
    principal = ZERO
    interest = ZERO
    penalty = ZERO
    penalty_charge = ZERO
    for leg in tx.entries.select_related("account").all():
        number = leg.account.account_number
        signed = leg.amount if leg.entry_type == JournalEntry.CREDIT else -leg.amount
        if number == "1300-LOAN_PRINCIPAL":
            principal = -signed
        elif number == "4001-INTEREST_INCOME":
            interest = signed
        elif number == "1310-LOAN_INTEREST":
            penalty = signed
        elif number == "4002-PENALTY_INCOME":
            penalty_charge = signed
    return principal, interest, penalty, penalty_charge


def run_loan_statement(loan, *, start=None, end=None):
    """Loan statement reconstructed from the journal.

    Outstanding principal is derived from the disbursement and repayment legs
    on ``1300-LOAN_PRINCIPAL`` (never from the cached loan columns — those are
    surfaced as the ``recorded_*`` crossing field only). Realised interest and
    penalty figures come straight off their income-account legs.
    """
    start_at, end_at = _parse_period(start, end)
    qs = (
        FinancialTransaction.objects.filter(loan=loan)
        .prefetch_related("entries", "entries__account")
        .annotate(posted_eff=Coalesce("posted_at", "created_at"))
    )

    opening_principal = ZERO
    if start_at:
        for tx in qs.filter(posted_eff__lt=start_at).order_by("posted_eff", "id"):
            principal, _, _, _ = _tx_loan_split(tx)
            opening_principal += principal
    opening_principal = _money(opening_principal)

    rows = []
    running = opening_principal
    disbursed = ZERO
    repaid_principal = ZERO
    repaid_interest = ZERO
    repaid_penalty = ZERO
    penalty_charges = ZERO

    scope = qs
    if start_at:
        scope = scope.filter(posted_eff__gte=start_at)
    if end_at:
        scope = scope.filter(posted_eff__lte=end_at)

    for tx in scope.order_by("posted_eff", "id"):
        principal, interest, penalty, penalty_charge = _tx_loan_split(tx)
        running += principal
        if tx.transaction_type == FinancialTransaction.TransactionType.LOAN_DISBURSEMENT:
            disbursed += tx.amount
        if interest > 0:
            repaid_interest += interest
        if penalty > 0:
            repaid_penalty += penalty
        if penalty_charge > 0:
            penalty_charges += penalty_charge
        if principal < 0:
            repaid_principal += -principal
        rows.append(
            {
                "date": (tx.posted_at or tx.created_at).isoformat(),
                "reference": tx.reference,
                "transaction_type": tx.transaction_type,
                "status": tx.status,
                "description": tx.description,
                "amount": str(tx.amount),
                "principal": str(_money(principal)),
                "interest": str(_money(interest)),
                "penalty": str(_money(penalty)),
                "penalty_charge": str(_money(penalty_charge)),
                "running_outstanding": str(_money(running)),
            }
        )

    closing = _money(running)
    return {
        "statement": "loan",
        "loan": {"id": loan.pk, "loan_number": loan.loan_number, "status": loan.status},
        "member": {
            "membership_number": loan.member.membership_number,
            "full_name": f"{loan.member.first_name} {loan.member.last_name}".strip(),
        },
        "currency": "TZS",
        "period": {
            "start": start_at.isoformat() if start_at else None,
            "end": end_at.isoformat() if end_at else None,
        },
        "opening_outstanding": str(opening_principal),
        "closing_outstanding": str(closing),
        "summary": {
            "transactions": len(rows),
            "disbursed": str(_money(disbursed)),
            "repaid_principal": str(_money(repaid_principal)),
            "repaid_interest": str(_money(repaid_interest)),
            "repaid_penalty": str(_money(repaid_penalty)),
            "penalty_charges": str(_money(penalty_charges)),
            "recorded_outstanding_principal": str(loan.outstanding_principal),
            "recorded_outstanding_interest": str(loan.outstanding_interest),
        },
        "rows": rows,
    }


def run_withdrawal_report(*, member=None, start=None, end=None, status=None):
    """Withdrawal report tying requests to WITHDRAWAL journal postings.

    Mirrors the contribution report: only a withdrawal with an actual ledger
    posting counts as paid; a SUCCESS-state request without a WITHDRAWAL leg is
    surfaced as ``unrecorded_in_ledger`` instead of silently reported as paid.
    """
    start_at, end_at = _parse_period(start, end)
    from accounts.models import WithdrawalRequest

    qs = WithdrawalRequest.objects.select_related("member", "account").all()
    if member is not None:
        qs = qs.filter(member=member)
    if status:
        qs = qs.filter(status=status)
    if start_at:
        qs = qs.filter(requested_at__gte=start_at)
    if end_at:
        qs = qs.filter(requested_at__lte=end_at)

    requests = list(qs.order_by("-requested_at"))
    ids = [req.pk for req in requests]

    ledger_by_request = (
        {
            tx.withdrawal_request_id: tx
            for tx in FinancialTransaction.objects.filter(
                withdrawal_request_id__in=ids or [None],
                transaction_type=FinancialTransaction.TransactionType.WITHDRAWAL,
            )
            .order_by("-posted_at", "-id")
        }
        if ids
        else {}
    )

    rows = []
    by_status = {}
    paid = ZERO
    for req in requests:
        tx = ledger_by_request.get(req.pk)
        paid_out = bool(tx)
        if paid_out:
            paid += tx.amount
        rows.append(
            {
                "reference": req.reference,
                "status": req.status,
                "member": {
                    "membership_number": req.member.membership_number,
                    "full_name": f"{req.member.first_name} {req.member.last_name}".strip(),
                },
                "amount": str(req.amount),
                "requested_at": req.requested_at.isoformat(),
                "processed_at": req.processed_at.isoformat() if req.processed_at else None,
                "paid_out": paid_out,
                "ledger": (
                    {
                        "amount": str(tx.amount),
                        "date": (tx.posted_at or tx.created_at).isoformat(),
                        "reference": tx.reference,
                    }
                    if tx
                    else None
                ),
            }
        )
        bucket = by_status.setdefault(req.status, {"count": 0, "amount": ZERO})
        bucket["count"] += 1
        bucket["amount"] += req.amount

    return {
        "statement": "withdrawals",
        "currency": "TZS",
        "period": {
            "start": start_at.isoformat() if start_at else None,
            "end": end_at.isoformat() if end_at else None,
        },
        "member": (
            {"membership_number": member.membership_number, "id": str(member.pk)}
            if member is not None
            else None
        ),
        "summary": {
            "requests": len(requests),
            "paid_out": str(paid),
            "unrecorded_in_ledger": len(requests) - len(ledger_by_request),
            "by_status": {
                k: {"count": v["count"], "amount": str(_money(v["amount"]))}
                for k, v in sorted(by_status.items())
            },
        },
        "rows": rows,
    }