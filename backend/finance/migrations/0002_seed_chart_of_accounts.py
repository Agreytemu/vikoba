from django.db import migrations

# (account_number, name, account_type, description)
CHART_OF_ACCOUNTS = [
    ("1000-SUSPENSE", "Suspense", "ASSET", "Clearing/suspense for unmatched funds."),
    ("1100-CLEARING", "Mobile Money Clearing", "ASSET", "Collections and payouts in transit via mobile money."),
    ("1200-GROUP_CASH", "Group Cash", "ASSET", "Cash held for group operations (platform-level default)."),
    ("1300-LOAN_PRINCIPAL", "Loan Principal Receivable", "ASSET", "Principal outstanding on disbursed loans."),
    ("1310-LOAN_INTEREST", "Loan Interest Receivable", "ASSET", "Interest receivable on disbursed loans."),
    ("2001-MEMBER_SAVINGS", "Member Savings", "LIABILITY", "Member savings deposits (liability to members)."),
    ("2002-WITHDRAWAL_PAYABLE", "Withdrawal Payable", "LIABILITY", "Withdrawals approved but not yet paid out."),
    ("4001-INTEREST_INCOME", "Interest Income", "INCOME", "Interest earned on loans."),
    ("4002-PENALTY_INCOME", "Penalty Income", "INCOME", "Fines and penalties collected from members."),
    ("4003-PLATFORM_FEE", "Platform Fee", "INCOME", "Platform/service fees."),
    ("4004-MEMBERSHIP_FEE", "Membership Fee", "INCOME", "Membership/subscription fees."),
    ("5001-PROVIDER_FEE", "Payment Provider Fee", "EXPENSE", "Mobile money provider fees."),
    ("5002-GROUP_EXPENSE", "Group Expense", "EXPENSE", "Group operating expenses."),
    ("5003-REFUND", "Refund", "EXPENSE", "Refunds issued to members."),
    ("5004-INTEREST_EXPENSE", "Interest Expense", "EXPENSE", "Interest accrued on member savings."),
]


def seed_chart_of_accounts(apps, schema_editor):
    FinancialAccount = apps.get_model("finance", "FinancialAccount")
    for account_number, name, account_type, description in CHART_OF_ACCOUNTS:
        FinancialAccount.objects.get_or_create(
            account_number=account_number,
            defaults={
                "name": name,
                "account_type": account_type,
                "currency": "TZS",
                "description": description,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_chart_of_accounts, migrations.RunPython.noop),
    ]