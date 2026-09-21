"""Loan repayment core: allocation, schedule settlement and the engine journal.

Both repayment entry points flow through :func:`post_repayment`:

- staff / member manual repayment (``loans.services.post_installment_repayment``)
  keeps the VICOBA member-savings WITHDRAWAL leg and then settles the loan;
- mobile-money repayment (``payments``) settles the loan directly, without a
  savings leg, and carries the provider ``PaymentTransaction`` on the journal.

Everything runs inside one database transaction with rows locked, so the loan
projections (``outstanding_principal/interest/penalty``) are kept consistent
with the double-entry journal for the same event.

Allocation order per installment: outstanding penalties first (oldest OPEN rows
first), then each open installment's interest leg, then its principal leg. An
installment is marked PAID once its cumulative paid amount reaches ``total_due``.
"""

from decimal import Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from finance.models import FinancialTransaction
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction

from .calculations import ZERO, _money
from .models import LoanAccount, LoanPenalty, LoanSchedule, LoanTransaction


def system_user():
    """Actor for automated/system ledger entries, mirroring the payments helper.

    Falls back to a superuser, creating the ``loans-system`` user only if the
    deployment has no superuser at all.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    admin = User.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
    if admin is not None:
        return admin
    user, _created = User.objects.get_or_create(
        username="loans-system",
        defaults={
            "email": "system@loans.local",
            "role": User.ADMIN,
            "is_active": True,
            "is_staff": True,
        },
    )
    return user


def _repayment_reference(loan):
    return f"REPAY-{loan.loan_number}-{uuid4().hex[:6].upper()}"


def _settle_penalties(*, loan, amount, user=None):
    """Settle OPEN penalty rows oldest-first; returns the amount consumed."""
    if amount <= 0:
        return ZERO
    remaining = _money(amount)
    settled = ZERO
    now = timezone.now()
    rows = (
        LoanPenalty.objects.select_for_update()
        .filter(loan=loan, status=LoanPenalty.Status.OPEN)
        .order_by("created_at", "id")
    )
    for penalty in rows:
        if remaining <= 0:
            break
        open_amount = _money(Decimal(penalty.amount) - Decimal(penalty.amount_paid))
        if open_amount <= 0:
            continue
        applied = min(open_amount, remaining)
        penalty.amount_paid = _money(Decimal(penalty.amount_paid) + applied)
        remaining = _money(remaining - applied)
        settled = _money(settled + applied)
        if penalty.amount_paid >= Decimal(penalty.amount):
            penalty.status = LoanPenalty.Status.PAID
            penalty.paid_at = now
        penalty.save(update_fields=["amount_paid", "status", "paid_at"])
    return settled


def _settle_installments(*, loan, amount, loan_tx, user=None, installment_number=None):
    """Apply cash to schedule installments (interest leg, then principal leg).

    With ``installment_number`` the settlement starts at that installment and
    then continues to later open rows (overpayments still clear the schedule).
    Returns ``(principal_paid, interest_paid, touched)``.
    """
    remaining = _money(amount)
    principal_paid = ZERO
    interest_paid = ZERO
    touched = []
    now = timezone.now()

    qs = LoanSchedule.objects.select_for_update().filter(loan=loan, is_paid=False)
    if installment_number is not None:
        anchor = qs.filter(installment_number=installment_number).first()
        if anchor is None:
            raise ValueError("That installment has already been paid.")
        rows = [anchor] + [
            row
            for row in (
                qs.filter(installment_number__gt=installment_number).order_by("installment_number")
            )
        ]
    else:
        rows = list(qs.order_by("installment_number"))

    for installment in rows:
        if remaining <= 0:
            break
        total_due = Decimal(installment.total_due)
        partial = Decimal(installment.partially_paid_amount)
        interest_due = Decimal(installment.interest_due)
        installment_due = _money(total_due - partial)
        if installment_due <= 0:
            continue

        applied = min(installment_due, remaining)
        remaining = _money(remaining - applied)

        interest_alloc = min(_money(interest_due - min(partial, interest_due)), applied)
        principal_alloc = _money(applied - interest_alloc)
        interest_paid = _money(interest_paid + interest_alloc)
        principal_paid = _money(principal_paid + principal_alloc)

        installment.partially_paid_amount = _money(partial + applied)
        if installment.partially_paid_amount >= total_due:
            installment.is_paid = True
            installment.paid_at = now
            installment.paid_by = user
            installment.payment_transaction = loan_tx
        installment.save(
            update_fields=[
                "partially_paid_amount",
                "is_paid",
                "paid_at",
                "paid_by",
                "payment_transaction",
            ]
        )
        touched.append(installment.installment_number)

    return principal_paid, interest_paid, touched


@transaction.atomic
def post_repayment(
    *,
    loan: LoanAccount,
    amount,
    user=None,
    narration="",
    payment_transaction=None,
    savings_transaction=None,
    installment_number=None,
    reference=None,
):
    """Allocate a repayment and post all its records + journal atomically.

    Returns ``(loan_transaction, allocation_dict)``. Idempotency is derived from
    the unique ``LoanTransaction`` reference (``rep-{reference}``), so replaying
    the same event can never post a second journal.
    """
    loan = LoanAccount.objects.select_for_update().get(pk=loan.pk)
    if loan.status != LoanAccount.DISBURSED:
        raise ValueError("Loan is not active.")

    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Repayment amount must be greater than zero.")
    if amount > loan.total_outstanding:
        raise ValueError("Repayment exceeds the outstanding obligation on this loan.")

    penalty_paid = _settle_penalties(loan=loan, amount=amount, user=user)
    remaining = _money(amount - penalty_paid)

    loan_tx = LoanTransaction.objects.create(
        loan=loan,
        transaction_type=LoanTransaction.REPAYMENT,
        amount=amount,
        reference=reference or _repayment_reference(loan),
        narration=narration or f"Loan repayment of {amount}",
        performed_by=user or system_user(),
    )

    principal_paid, interest_paid, touched = _settle_installments(
        loan=loan,
        amount=remaining,
        loan_tx=loan_tx,
        user=user,
        installment_number=installment_number,
    )
    applied = _money(penalty_paid + principal_paid + interest_paid)

    loan.outstanding_principal = max(ZERO, Decimal(loan.outstanding_principal) - principal_paid)
    loan.outstanding_interest = max(ZERO, Decimal(loan.outstanding_interest) - interest_paid)
    loan.outstanding_penalty = max(ZERO, Decimal(loan.outstanding_penalty) - penalty_paid)
    loan.save(
        update_fields=[
            "outstanding_principal",
            "outstanding_interest",
            "outstanding_penalty",
        ]
    )

    if (
        not loan.schedule.filter(is_paid=False).exists()
        and loan.outstanding_principal == 0
        and loan.outstanding_interest == 0
        and loan.outstanding_penalty == 0
    ):
        loan.complete()

    entries = [
        {
            "account": get_org_account("1100-CLEARING"),
            "entry_type": "DEBIT",
            "amount": applied,
        }
    ]
    if principal_paid > 0:
        entries.append(
            {
                "account": get_org_account("1300-LOAN_PRINCIPAL"),
                "entry_type": "CREDIT",
                "amount": principal_paid,
            }
        )
    if interest_paid > 0:
        entries.append(
            {
                "account": get_org_account("4001-INTEREST_INCOME"),
                "entry_type": "CREDIT",
                "amount": interest_paid,
            }
        )
    if penalty_paid > 0:
        entries.append(
            {
                "account": get_org_account("1310-LOAN_INTEREST"),
                "entry_type": "CREDIT",
                "amount": penalty_paid,
            }
        )

    post_transaction(
        transaction_type=FinancialTransaction.TransactionType.LOAN_REPAYMENT,
        amount=applied,
        group=getattr(loan.application, "group", None),
        member=loan.member,
        description=narration or f"Repayment on {loan.loan_number}",
        idempotency_key=f"rep-{loan_tx.reference}",
        initiated_by=user,
        payment_transaction=payment_transaction,
        savings_transaction=savings_transaction,
        loan=loan,
        entries=entries,
    )

    return loan_tx, {
        "amount": applied,
        "penalty_paid": penalty_paid,
        "interest_paid": interest_paid,
        "principal_paid": principal_paid,
        "installments_touched": touched,
    }