"""Pure loan math: repayment scheduling, payment allocation and balance truth.

These are side-effect-free helpers. Every financial mutation (disbursement,
repayment allocation, penalty application) lives in the sibling modules and the
engine-backed journals in :mod:`loans.repayments` / :mod:`loans.penalties`.
"""
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models import LoanAccount, LoanProduct

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value):
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def build_installments(*, principal, annual_rate, months, interest_type):
    """Build the monthly installments for a loan.

    Returns a list of ``(principal_due, interest_due, total_due)`` tuples. The
    amount math mirrors the existing product behaviour (Flat and Reducing
    Balance) so existing schedules are bit-for-bit identical.
    """
    principal = Decimal(principal)
    annual_rate = Decimal(annual_rate) / Decimal("100")
    months = int(months)
    rows = []

    if interest_type == LoanProduct.FLAT:
        total_interest = _money(principal * annual_rate * Decimal(months) / Decimal("12"))
        monthly_principal = _money(principal / months)
        monthly_interest = _money(total_interest / months)
        principal_remaining = principal
        interest_remaining = total_interest
        for number in range(1, months + 1):
            principal_due = principal_remaining if number == months else monthly_principal
            interest_due = interest_remaining if number == months else monthly_interest
            rows.append((principal_due, interest_due, _money(principal_due + interest_due)))
            principal_remaining -= principal_due
            interest_remaining -= interest_due
    else:
        monthly_rate = annual_rate / Decimal("12")
        payment = _money(principal / months) if not monthly_rate else _money(
            principal * monthly_rate / (Decimal("1") - (Decimal("1") + monthly_rate) ** -months)
        )
        principal_remaining = principal
        for number in range(1, months + 1):
            interest_due = _money(principal_remaining * monthly_rate)
            principal_due = principal_remaining if number == months else _money(payment - interest_due)
            rows.append((principal_due, interest_due, _money(principal_due + interest_due)))
            principal_remaining -= principal_due

    return rows


def schedule_rows(*, loan):
    """Schedule rows for an already-disbursed loan (disbursement date start)."""
    return build_installments(
        principal=loan.principal_amount,
        annual_rate=loan.interest_rate,
        months=loan.term_months,
        interest_type=loan.product.interest_type,
    )


def expected_due_dates(*, disbursed_on, months):
    """The ``months`` due dates after a disbursement date."""
    return [_add_months(disbursed_on, n) for n in range(1, months + 1)]


def authoritative_balance(*, outstanding_principal, outstanding_interest, outstanding_penalty):
    """The loan's total obligation at any point in time."""
    return _money(
        Decimal(outstanding_principal) + Decimal(outstanding_interest) + Decimal(outstanding_penalty)
    )