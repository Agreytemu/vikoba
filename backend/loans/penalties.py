"""Overdue detection and penalty charging with ledger-backed idempotency."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from finance.models import FinancialTransaction
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction

from .calculations import _money
from .models import LoanAccount, LoanPenalty, LoanSchedule
from .repayments import system_user


def _default_penalty_rate():
    return Decimal(str(getattr(settings, "LOAN_PENALTY_RATE", "0.00")))


def _default_penalty_grace_days():
    return int(getattr(settings, "LOAN_PENALTY_GRACE_DAYS", 7))


def overdue_installments(loan, *, as_of=None, grace_days=0):
    """Unpaid installments whose lateness exceeds the grace window."""
    today = as_of or timezone.now().date()
    rows = (
        LoanSchedule.objects.filter(loan=loan, is_paid=False, due_date__lt=today)
        .order_by("installment_number")
    )
    return [row for row in rows if (today - row.due_date).days > grace_days]


@transaction.atomic
def charge_penalty(
    *,
    loan: LoanAccount,
    installment: LoanSchedule,
    penalty_rate=None,
    grace_days=None,
    user=None,
    as_of=None,
):
    """Charge one penalty against an overdue installment (idempotent).

    Safe to run repeatedly: an existing OPEN penalty for the same installment
    is returned untouched (unique constraint + keyed journal), so a rerun of the
    management command can never double-charge.
    """
    today = as_of or timezone.now().date()
    overdue_days = (today - installment.due_date).days
    if installment.is_paid or overdue_days <= (grace_days or _default_penalty_grace_days()):
        return None

    rate = Decimal(penalty_rate if penalty_rate is not None else _default_penalty_rate())
    amount = _money(Decimal(installment.principal_due) * rate / Decimal("100"))
    if amount <= 0:
        return None

    loan = LoanAccount.objects.select_for_update().get(pk=loan.pk)
    if loan.status != LoanAccount.DISBURSED:
        return None
    installed = LoanSchedule.objects.select_for_update().get(pk=installment.pk)
    if installed.is_paid:
        return None

    existing = LoanPenalty.objects.filter(loan=loan, installment=installed).first()
    if existing is not None:
        return existing

    penalty = LoanPenalty.objects.create(
        loan=loan,
        installment=installed,
        amount=amount,
        reason=(
            f"Overdue installment {installed.installment_number}: "
            f"{overdue_days} day(s) past due."
        ),
        created_by=user or system_user(),
    )

    loan.outstanding_penalty = _money(loan.outstanding_penalty + amount)
    loan.save(update_fields=["outstanding_penalty"])

    post_transaction(
        transaction_type=FinancialTransaction.TransactionType.PENALTY,
        amount=amount,
        group=getattr(loan.application, "group", None),
        member=loan.member,
        description=penalty.reason[:255],
        idempotency_key=f"penalty-{loan.loan_number}-{installed.installment_number}",
        initiated_by=user,
        loan=loan,
        entries=[
            {
                "account": get_org_account("1310-LOAN_INTEREST"),
                "entry_type": "DEBIT",
                "amount": amount,
            },
            {
                "account": get_org_account("4002-PENALTY_INCOME"),
                "entry_type": "CREDIT",
                "amount": amount,
            },
        ],
    )
    return penalty


def process_overdue_loans(*, as_of=None, user=None, penalty_rate=None, grace_days=None):
    """Run penalty charging for every active disbursed loan (idempotent).

    Only newly-created penalties are returned; installments that already carry
    an OPEN penalty are skipped so running the nightly command repeatedly never
    re-reports the same charges.
    """
    today = as_of or timezone.now().date()
    charged = []
    for loan in LoanAccount.objects.filter(status=LoanAccount.DISBURSED).select_related("application"):
        for installment in overdue_installments(
            loan,
            as_of=today,
            grace_days=grace_days or _default_penalty_grace_days(),
        ):
            if LoanPenalty.objects.filter(loan=loan, installment=installment).exists():
                continue
            penalty = charge_penalty(
                loan=loan,
                installment=installment,
                penalty_rate=penalty_rate,
                grace_days=grace_days,
                user=user or system_user(),
                as_of=today,
            )
            if penalty is not None:
                charged.append((loan, installment, penalty))
    return charged