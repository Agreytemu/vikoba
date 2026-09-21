"""Canonical VICOBA chart of accounts seeded for Phase 1.

Only accounts actually required by the existing business model are created.
Organization-level accounts are seeded once; member/group/loan-scoped accounts
are created lazily by the transaction engine as business objects appear.
"""
from finance.models import FinancialAccount

# (account_number, name, account_type, description)
CHART_OF_ACCOUNTS = [
    (
        "1000-SUSPENSE",
        "Suspense",
        FinancialAccount.AccountType.ASSET,
        "Clearing/suspense for unmatched funds.",
    ),
    (
        "1100-CLEARING",
        "Mobile Money Clearing",
        FinancialAccount.AccountType.ASSET,
        "Collections and payouts in transit via mobile money.",
    ),
    (
        "1200-GROUP_CASH",
        "Group Cash",
        FinancialAccount.AccountType.ASSET,
        "Cash held for group operations (platform-level default).",
    ),
    (
        "1300-LOAN_PRINCIPAL",
        "Loan Principal Receivable",
        FinancialAccount.AccountType.ASSET,
        "Principal outstanding on disbursed loans.",
    ),
    (
        "1310-LOAN_INTEREST",
        "Loan Interest Receivable",
        FinancialAccount.AccountType.ASSET,
        "Interest receivable on disbursed loans.",
    ),
    (
        "2001-MEMBER_SAVINGS",
        "Member Savings",
        FinancialAccount.AccountType.LIABILITY,
        "Member savings deposits (liability to members).",
    ),
    (
        "2002-WITHDRAWAL_PAYABLE",
        "Withdrawal Payable",
        FinancialAccount.AccountType.LIABILITY,
        "Withdrawals approved but not yet paid out.",
    ),
    (
        "4001-INTEREST_INCOME",
        "Interest Income",
        FinancialAccount.AccountType.INCOME,
        "Interest earned on loans.",
    ),
    (
        "4002-PENALTY_INCOME",
        "Penalty Income",
        FinancialAccount.AccountType.INCOME,
        "Fines and penalties collected from members.",
    ),
    (
        "4003-PLATFORM_FEE",
        "Platform Fee",
        FinancialAccount.AccountType.INCOME,
        "Platform/service fees.",
    ),
    (
        "4004-MEMBERSHIP_FEE",
        "Membership Fee",
        FinancialAccount.AccountType.INCOME,
        "Membership/subscription fees.",
    ),
    (
        "5001-PROVIDER_FEE",
        "Payment Provider Fee",
        FinancialAccount.AccountType.EXPENSE,
        "Mobile money provider fees.",
    ),
    (
        "5002-GROUP_EXPENSE",
        "Group Expense",
        FinancialAccount.AccountType.EXPENSE,
        "Group operating expenses.",
    ),
    (
        "5003-REFUND",
        "Refund",
        FinancialAccount.AccountType.EXPENSE,
        "Refunds issued to members.",
    ),
    (
        "5004-INTEREST_EXPENSE",
        "Interest Expense",
        FinancialAccount.AccountType.EXPENSE,
        "Interest accrued on member savings.",
    ),
]


def seed_chart_of_accounts():
    """Idempotent creation of the organization-level chart of accounts."""
    created = 0
    for account_number, name, account_type, description in CHART_OF_ACCOUNTS:
        _, was_created = FinancialAccount.objects.get_or_create(
            account_number=account_number,
            defaults={
                "name": name,
                "account_type": account_type,
                "currency": "TZS",
                "description": description,
            },
        )
        created += int(was_created)
    return created


def get_account(account_number):
    return FinancialAccount.objects.get(account_number=account_number)