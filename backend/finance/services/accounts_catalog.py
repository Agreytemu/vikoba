"""Resolver for financial accounts.

Organization-level accounts come from the seeded chart of accounts. Accounts
that follow a business object (a member's savings, a group's cash, a loan's
receivables) are created lazily — and idempotently — on first use so the double
entry always posts against a real, scoped account.
"""
from django.db import transaction

from finance.models import FinancialAccount

ZERO = "0.00"


def get_org_account(account_number: str) -> FinancialAccount:
    try:
        return FinancialAccount.objects.get(account_number=account_number)
    except FinancialAccount.DoesNotExist:
        raise _account_missing(account_number)


def get_or_create_member_savings_account(savings_account) -> FinancialAccount:
    """One MEMBER_SAVINGS liability account per operational savings account."""
    existing = getattr(savings_account, "financial_account", None)
    if existing is not None:
        return existing
    with transaction.atomic():
        account, _ = FinancialAccount.objects.select_for_update().get_or_create(
            savings_account=savings_account,
            defaults={
                "account_number": f"MS-{savings_account.account_number}",
                "name": f"Savings - {savings_account.member.membership_number}",
                "account_type": FinancialAccount.AccountType.LIABILITY,
                "currency": "TZS",
                "member": savings_account.member,
                "description": "Member savings liability account.",
            },
        )
    return account


def get_or_create_group_cash_account(group) -> FinancialAccount:
    """Group-scoped cash account for group transactions."""
    with transaction.atomic():
        account, _ = FinancialAccount.objects.select_for_update().get_or_create(
            group=group,
            name="Group Cash",
            account_type=FinancialAccount.AccountType.ASSET,
            defaults={
                "account_number": f"GC-{group.pk}",
                "currency": "TZS",
                "description": f"Cash for group {group.pk}.",
            },
        )
    return account


def get_or_create_loan_principal_account(loan) -> FinancialAccount:
    with transaction.atomic():
        account, _ = FinancialAccount.objects.select_for_update().get_or_create(
            loan_account=loan,
            name="Loan Principal Receivable",
            account_type=FinancialAccount.AccountType.ASSET,
            defaults={
                "account_number": f"LR-{loan.loan_number}",
                "currency": "TZS",
                "member": loan.member,
                "description": f"Loan principal receivable for {loan.loan_number}.",
            },
        )
    return account


def get_or_create_loan_interest_account(loan) -> FinancialAccount:
    with transaction.atomic():
        account, _ = FinancialAccount.objects.select_for_update().get_or_create(
            loan_account=loan,
            name="Loan Interest Receivable",
            account_type=FinancialAccount.AccountType.ASSET,
            defaults={
                "account_number": f"LR-{loan.loan_number}-INT",
                "currency": "TZS",
                "member": loan.member,
                "description": f"Loan interest receivable for {loan.loan_number}.",
            },
        )
    return account


def _account_missing(account_number):
    from finance.services.engine import FinancialError

    return FinancialError(
        code=FinancialError.ACCOUNT_NOT_FOUND,
        message=f"Financial account {account_number} does not exist.",
    )