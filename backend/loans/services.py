from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import SavingsTransaction
from accounts.services import post_savings_transaction
from finance.models import AuditEvent, FinancialTransaction
from finance.services.accounts_catalog import get_org_account
from finance.services.engine import post_transaction

from .calculations import ZERO, _money, build_installments, expected_due_dates
from .eligibility import check_eligibility
from .models import (
    LoanAccount,
    LoanApplication,
    LoanProduct,
    LoanSchedule,
    LoanTransaction,
)
from .policies import effective_values
from .repayments import post_repayment


MINIMUM_MEMBERSHIP_MONTHS = getattr(settings, "LOAN_MINIMUM_MEMBERSHIP_MONTHS", 3)
MINIMUM_MONTHLY_CONTRIBUTION = Decimal(
    str(getattr(settings, "LOAN_MINIMUM_MONTHLY_CONTRIBUTION", "0.00"))
)
DEFAULT_LOAN_MULTIPLIER = Decimal("3.00")


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def _audit_loan(*, action, reference, user=None, loan=None, **metadata):
    return AuditEvent.objects.create(
        user=user,
        action=action,
        reference=reference,
        transaction=None,
        metadata={**metadata, "loan": getattr(loan, "loan_number", None)},
    )


def infer_group(application: LoanApplication):
    """Attach the member's first active group membership to the application.

    Group lending rules only apply once the application is tied to a group;
    applications without a group keep product-level behaviour (and skip the
    group capacity gate).
    """
    if application.group_id:
        return application.group
    from groups.models import GroupMembership

    membership = (
        GroupMembership.objects.filter(member=application.member, is_active=True)
        .order_by("joined_at", "id")
        .first()
    )
    if membership is not None:
        application.group = membership.group
        application.save(update_fields=["group"])
    return application.group


def create_repayment_schedule(*, loan: LoanAccount):
    """Create monthly installments using the product's configured interest method."""
    rows = build_installments(
        principal=loan.principal_amount,
        annual_rate=loan.interest_rate,
        months=loan.term_months,
        interest_type=loan.interest_type,
    )
    schedules = [
        LoanSchedule(
            loan=loan,
            installment_number=number,
            due_date=due_date,
            principal_due=principal_due,
            interest_due=interest_due,
            total_due=total_due,
        )
        for number, (principal_due, interest_due, total_due), due_date in zip(
            range(1, len(rows) + 1),
            rows,
            expected_due_dates(disbursed_on=loan.disbursed_at.date(), months=len(rows)),
        )
    ]
    LoanSchedule.objects.bulk_create(schedules)
    return schedules


def approve_application(*, application, user, notes="", approved_amount=None):
    """Authoritative approval: re-checks every blocking eligibility rule, then
    records the final approved amount. Group capacity is enforced under a lock
    on the group row so concurrent approvals cannot exceed the cap.
    """
    with transaction.atomic():
        app = (
            LoanApplication.objects.select_for_update()
            .select_related("member", "loan_type", "group")
            .get(pk=application.pk)
        )
        if app.status != LoanApplication.Status.UNDER_REVIEW:
            raise ValueError("Only applications under review can be approved.")

        amount = _money(approved_amount if approved_amount is not None else app.requested_amount)

        if app.group_id is not None:
            from groups.models import VikobaGroup

            VikobaGroup.objects.select_for_update().get(pk=app.group_id)

        ok, errors = check_eligibility(app, approved_amount=amount)
        if not ok:
            raise ValueError("; ".join(errors))

        app.approved_amount = amount
        app.approve(user, notes)
        loan_ref = LoanAccount.objects.filter(application=app).first()
        _audit_loan(
            action="loan.application.approved",
            reference=app.application_number,
            user=user,
            loan=loan_ref,
            approved_amount=str(amount),
            requested_amount=str(app.requested_amount),
            notes=notes,
        )
        _record_governance_loan_decision(application=app, user=user, action="approved", reason=notes, approved_amount=amount)
    return app


def _record_governance_loan_decision(*, application, user, action, reason="", approved_amount=None):
    """Best-effort governance observation; never blocks the loan flow."""
    try:
        from governance.loans import record_loan_decision

        record_loan_decision(
            application=application,
            user=user,
            action=action,
            reason=reason or "",
            approved_amount=approved_amount,
        )
    except Exception:  # noqa: BLE001
        pass


def post_installment_repayment(*, loan: LoanAccount, installment_number: int, account, user, narration="", amount=None):
    """Debit a member savings account and settle one scheduled installment.

    The VICOBA member-savings leg is preserved (the tests and existing ledger
    semantics rely on the WITHDRAWAL row); the loan settlement itself runs
    through the shared :func:`post_repayment` core. ``amount`` defaults to the
    installment's full ``total_due``; pass a lower ``amount`` to make a partial
    repayment (the remainder stays due on the installment).
    """
    with transaction.atomic():
        loan = LoanAccount.objects.select_for_update().get(pk=loan.pk)
        if loan.status != LoanAccount.DISBURSED:
            raise ValueError("Loan is not active.")
        installment = LoanSchedule.objects.select_for_update().get(loan=loan, installment_number=installment_number)
        if installment.is_paid:
            raise ValueError("This installment has already been paid.")

        pay_amount = _money(amount if amount is not None else installment.total_due)
        if pay_amount <= 0:
            raise ValueError("Repayment amount must be greater than zero.")
        if pay_amount > loan.total_outstanding:
            raise ValueError("Repayment exceeds the outstanding obligation on this loan.")

        savings_txn = post_savings_transaction(
            account=account,
            transaction_type=SavingsTransaction.WITHDRAWAL,
            amount=pay_amount,
            user=user,
            narration=narration or f"Loan {loan.loan_number} installment {installment.installment_number}",
        )

        post_repayment(
            loan=loan,
            amount=pay_amount,
            user=user,
            narration=narration or f"Installment {installment.installment_number} repayment",
            savings_transaction=savings_txn,
            installment_number=installment_number,
        )
        return loan.schedule.get(installment_number=installment_number)


def _months_between(start_date, end_date):
    return max(0, (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month))


def build_eligibility_summary(application: LoanApplication):
    member = application.member
    today = timezone.now().date()
    membership_months = _months_between(member.date_joined, today)
    deposits = member.accounts.aggregate(total=Sum("balance")).get("total") or Decimal("0.00")
    monthly_contribution = (
        SavingsTransaction.objects.filter(
            account__member=member,
            transaction_type=SavingsTransaction.DEPOSIT,
            created_at__date__gte=today.replace(day=1),
        ).aggregate(total=Sum("amount")).get("total")
        or Decimal("0.00")
    )
    values = effective_values(application.group, application.loan_type)
    multiplier = values["multiplier"] or DEFAULT_LOAN_MULTIPLIER
    eligible_amount = deposits * multiplier
    active_loans = LoanAccount.objects.filter(
        member=member,
        status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED, LoanAccount.DEFAULTED],
    )
    outstanding_balance = active_loans.aggregate(total=Sum("outstanding_principal")).get("total") or Decimal("0.00")
    total_guaranteed = application.guarantors.aggregate(total=Sum("guaranteed_amount")).get("total") or Decimal("0.00")

    estimated_monthly_installment = Decimal("0.00")
    estimated_total_interest = Decimal("0.00")
    estimated_total_repayable = application.requested_amount
    if application.repayment_period_months:
        months = application.repayment_period_months
        annual_rate = values["interest_rate"] / Decimal("100")
        interest_type = values["interest_type"]
        if interest_type == LoanProduct.FLAT:
            estimated_total_interest = _money(
                application.requested_amount * annual_rate * Decimal(months) / Decimal("12")
            )
            estimated_total_repayable = application.requested_amount + estimated_total_interest
            estimated_monthly_installment = _money(estimated_total_repayable / months)
        else:
            monthly_rate = annual_rate / Decimal("12")
            estimated_monthly_installment = _money(application.requested_amount / months) if not monthly_rate else _money(
                application.requested_amount * monthly_rate /
                (Decimal("1") - (Decimal("1") + monthly_rate) ** -months)
            )
            estimated_total_repayable = estimated_monthly_installment * months
            estimated_total_interest = estimated_total_repayable - application.requested_amount

    two_thirds_salary_limit = None
    if application.gross_salary:
        two_thirds_salary_limit = (application.gross_salary * Decimal("2")) / Decimal("3")

    warnings = []
    if membership_months < MINIMUM_MEMBERSHIP_MONTHS:
        warnings.append({
            "code": "membership_duration",
            "message": f"Member has only been active for {membership_months} months. Minimum recommended period is {MINIMUM_MEMBERSHIP_MONTHS} months.",
        })

    if MINIMUM_MONTHLY_CONTRIBUTION > 0 and monthly_contribution < MINIMUM_MONTHLY_CONTRIBUTION:
        warnings.append({
            "code": "monthly_contribution",
            "message": (
                f"Monthly contribution of {monthly_contribution} is below the "
                f"recommended minimum of {MINIMUM_MONTHLY_CONTRIBUTION}."
            ),
        })

    if application.requested_amount > eligible_amount:
        warnings.append({
            "code": "loan_multiplier",
            "message": f"Requested amount exceeds the indicative eligibility limit of {eligible_amount} based on deposits and multiplier.",
        })

    if active_loans.exists() and outstanding_balance > 0:
        warnings.append({
            "code": "existing_loans",
            "message": f"Member has {active_loans.count()} active loan(s) with outstanding balance {outstanding_balance}.",
        })

    if two_thirds_salary_limit is not None and estimated_monthly_installment > two_thirds_salary_limit:
        warnings.append({
            "code": "salary_rule",
            "message": "Estimated monthly installment exceeds the two-thirds gross salary guideline.",
        })

    if application.security_type != LoanApplication.SecurityType.COLLATERAL:
        self_guaranteed = application.requested_amount <= deposits
        if not self_guaranteed and total_guaranteed < application.requested_amount:
            warnings.append({
                "code": "guarantors",
                "message": "Total guaranteed amount is below the requested loan amount.",
            })

    return {
        "membership_date": member.date_joined,
        "membership_months": membership_months,
        "current_deposits": deposits,
        "monthly_contribution": monthly_contribution,
        "minimum_monthly_contribution": MINIMUM_MONTHLY_CONTRIBUTION,
        "loan_multiplier": multiplier,
        "eligible_amount": eligible_amount,
        "active_loans": active_loans.count(),
        "outstanding_balance": outstanding_balance,
        "estimated_monthly_installment": estimated_monthly_installment,
        "estimated_total_interest": estimated_total_interest,
        "estimated_total_repayable": estimated_total_repayable,
        "two_thirds_salary_limit": two_thirds_salary_limit,
        "total_guaranteed": total_guaranteed,
        "warnings": warnings,
    }


def compute_member_eligibility(member):
    """How much a member can borrow right now, based on deposits and contributions.

    Estimates the indicative eligible amount (deposits x multiplier) and, when a
    product is provided via query params, an illustrative installment for the
    chosen amount/term. Used by the member self-service calculator.
    """
    today = timezone.now().date()
    membership_months = _months_between(member.date_joined, today)
    deposits = member.accounts.aggregate(total=Sum("balance")).get("total") or Decimal("0.00")
    monthly_contribution = (
        SavingsTransaction.objects.filter(
            account__member=member,
            transaction_type=SavingsTransaction.DEPOSIT,
            created_at__date__gte=today.replace(day=1),
        ).aggregate(total=Sum("amount")).get("total")
        or Decimal("0.00")
    )
    active_loans = LoanAccount.objects.filter(
        member=member,
        status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED, LoanAccount.DEFAULTED],
    )
    outstanding_balance = active_loans.aggregate(total=Sum("outstanding_principal")).get("total") or Decimal("0.00")

    products = [
        {
            "id": product.id,
            "name": product.name,
            "interest_rate": product.interest_rate,
            "interest_type": product.interest_type,
            "multiplier": product.multiplier or DEFAULT_LOAN_MULTIPLIER,
            "min_amount": product.min_amount,
            "max_amount": product.max_amount,
            "max_term_months": product.max_term_months,
            "requires_guarantors": product.requires_guarantors,
            "eligible_amount": _money(deposits * (product.multiplier or DEFAULT_LOAN_MULTIPLIER)),
        }
        for product in LoanProduct.objects.filter(is_active=True).order_by("name")
    ]

    return {
        "membership_date": member.date_joined,
        "membership_months": membership_months,
        "current_deposits": deposits,
        "monthly_contribution": monthly_contribution,
        "loan_multiplier": DEFAULT_LOAN_MULTIPLIER,
        "active_loans": active_loans.count(),
        "outstanding_balance": outstanding_balance,
        "products": products,
        "warnings": [
            {
                "code": "membership_duration",
                "message": f"Member has only been active for {membership_months} months. Minimum recommended period is {MINIMUM_MEMBERSHIP_MONTHS} months.",
            }
            if membership_months < MINIMUM_MEMBERSHIP_MONTHS
            else None,
            {
                "code": "monthly_contribution",
                "message": (
                    f"Monthly contribution of {monthly_contribution} is below the "
                    f"recommended minimum of {MINIMUM_MONTHLY_CONTRIBUTION}."
                ),
            }
            if MINIMUM_MONTHLY_CONTRIBUTION > 0 and monthly_contribution < MINIMUM_MONTHLY_CONTRIBUTION
            else None,
            {
                "code": "existing_loans",
                "message": f"Member has {active_loans.count()} active loan(s) with outstanding balance {outstanding_balance}.",
            }
            if active_loans.exists() and outstanding_balance > 0
            else None,
        ],
    }


def disburse_application(*, application: LoanApplication, account, user, notes=""):
    with transaction.atomic():
        # Lock the application first so two approval requests cannot credit the
        # member account twice. The account service locks the account row itself.
        application = (
            LoanApplication.objects.select_for_update()
            .select_related("member", "loan_type", "group")
            .get(pk=application.pk)
        )

        if application.status != LoanApplication.Status.APPROVED:
            raise ValueError("Only approved applications can be disbursed.")

        if LoanAccount.objects.filter(application=application).exists():
            raise ValueError("This application has already been disbursed.")

        if account.member_id != application.member_id:
            raise ValueError("Disbursement account must belong to the application member.")

        principal = _money(application.approved_amount or application.requested_amount)
        values = effective_values(application.group, application.loan_type)

        loan_account = LoanAccount.objects.create(
            application=application,
            member=application.member,
            product=application.loan_type,
            principal_amount=principal,
            interest_rate=values["interest_rate"],
            interest_type=values["interest_type"],
            penalty_rate=values["penalty_rate"],
            term_months=application.repayment_period_months,
            approved_at=application.approved_at,
            disbursed_at=timezone.now(),
            status=LoanAccount.DISBURSED,
            outstanding_principal=principal,
            outstanding_interest=Decimal("0.00"),
            created_by=application.created_by,
        )

        post_savings_transaction(
            account=account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=principal,
            user=user,
            narration=notes or f"Loan disbursement for {application.application_number}",
        )

        post_transaction(
            transaction_type=FinancialTransaction.TransactionType.LOAN_DISBURSEMENT,
            amount=principal,
            group=application.group,
            member=application.member,
            description=f"Loan disbursement {application.application_number}",
            idempotency_key=f"disb-{application.application_number}",
            initiated_by=user,
            loan=loan_account,
            entries=[
                {
                    "account": get_org_account("1300-LOAN_PRINCIPAL"),
                    "entry_type": "DEBIT",
                    "amount": principal,
                },
                {
                    "account": get_org_account("1100-CLEARING"),
                    "entry_type": "CREDIT",
                    "amount": principal,
                },
            ],
        )

        LoanTransaction.objects.create(
            loan=loan_account,
            transaction_type=LoanTransaction.DISBURSEMENT,
            amount=principal,
            reference=f"LTX-{application.application_number}",
            narration=notes or f"Loan disbursement to {account.account_number}",
            performed_by=user,
        )

        schedule = create_repayment_schedule(loan=loan_account)
        loan_account.outstanding_interest = sum(
            (item.interest_due for item in schedule), Decimal("0.00")
        )
        loan_account.save(update_fields=["outstanding_interest"])

        _audit_loan(
            action="loan.disbursed",
            reference=application.application_number,
            user=user,
            loan=loan_account,
            amount=str(principal),
            account=account.account_number,
            notes=notes,
        )

        application.status = LoanApplication.Status.DISBURSED
        application.disbursed_by = user
        application.disbursed_at = timezone.now()
        application.disbursement_notes = notes
        application.save(update_fields=[
            "status",
            "disbursed_by",
            "disbursed_at",
            "disbursement_notes",
        ])

    return loan_account