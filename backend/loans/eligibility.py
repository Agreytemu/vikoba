"""Service-level eligibility gate for loan approvals.

Soft checks (membership duration, monthly contribution, salary rule) remain as
informational warnings surfaced to staff through ``build_eligibility_summary``;
this module holds the BLOCKING checks the backend enforces at approval time so
the decision is authoritative and not frontend-driven.
"""

from decimal import Decimal

from django.db.models import Sum

from accounts.models import SavingsAccount

from .models import LoanAccount, LoanApplication
from .policies import capacity_available, effective_values

ZERO = Decimal("0.00")


def _kyc_satisfied(member, kyc_level) -> bool:
    from kyc import services as kyc_services

    return kyc_services.satisfies(member, kyc_level)


def check_eligibility(application: LoanApplication, *, approved_amount=None):
    """Evaluate every blocking rule for an application.

    Returns ``(ok: bool, errors: list[str])``. ``approved_amount`` may differ
    from ``requested_amount``; all amount checks run against the final amount.
    """
    errors = []
    amount = Decimal(approved_amount if approved_amount is not None else application.requested_amount)
    member = application.member
    product = application.loan_type
    values = effective_values(application.group, product)

    kyc_level = values["kyc_level_required"]
    if not _kyc_satisfied(member, kyc_level):
        errors.append(
            f"The member does not satisfy the required {kyc_level} KYC verification level."
        )

    if amount < product.min_amount:
        errors.append(
            f"Requested amount is below the minimum of {product.min_amount} for {product.name}."
        )
    if amount > values["max_amount"]:
        errors.append(
            f"Requested amount exceeds the maximum of {values['max_amount']} for {product.name}."
        )
    if application.repayment_period_months > values["max_term_months"]:
        errors.append(
            f"Repayment term exceeds the maximum of {values['max_term_months']} months."
        )

    deposits = (
        member.accounts.aggregate(total=Sum("balance")).get("total") or ZERO
    )
    eligible = Decimal(deposits) * Decimal(values["multiplier"])
    if amount > eligible:
        errors.append(
            f"Requested amount of {amount} exceeds the eligible limit of {eligible} "
            f"based on deposits and the multiplier of {values['multiplier']}."
        )

    active_loans = LoanAccount.objects.filter(
        member=member,
        status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED, LoanAccount.DEFAULTED],
        outstanding_principal__gt=ZERO,
    )
    if active_loans.exists():
        balance = active_loans.aggregate(total=Sum("outstanding_principal")).get("total") or ZERO
        errors.append(
            f"Member already has {active_loans.count()} active loan(s) with outstanding balance {balance}."
        )

    approved_pending = LoanApplication.objects.filter(
        member=member,
        status=LoanApplication.Status.APPROVED,
    ).exclude(pk=application.pk)
    if approved_pending.exists():
        errors.append(
            "Member already has an approved application awaiting disbursement "
            f"({approved_pending.first().application_number})."
        )

    if values["requires_guarantors"] and application.security_type != LoanApplication.SecurityType.COLLATERAL:
        total_guaranteed = (
            application.guarantors.aggregate(total=Sum("guaranteed_amount")).get("total") or ZERO
        )
        self_guaranteed = amount <= deposits
        if not self_guaranteed and Decimal(total_guaranteed) < amount:
            errors.append(
                f"Guarantor coverage of {total_guaranteed} is below the required {amount}."
            )

    if application.group is not None and values["group_capacity_enabled"]:
        ok, capacity = capacity_available(application.group, amount)
        if not ok:
            errors.append(
                "The group does not have enough lending capacity for this loan "
                f"(remaining capacity {capacity['remaining_capacity']})."
            )

    return len(errors) == 0, errors