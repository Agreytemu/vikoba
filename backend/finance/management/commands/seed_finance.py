"""Idempotent finance priming: seed the chart of accounts and (optionally) the
per-member-savings financial accounts. Safe to run any number of times.
"""
from django.core.management.base import BaseCommand

from finance.chart import seed_chart_of_accounts
from finance.services.accounts_catalog import get_or_create_member_savings_account


class Command(BaseCommand):
    help = "Seed the chart of accounts and finance scaffolding."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backfill-member-savings",
            action="store_true",
            help="Create a financial account for every operational savings account.",
        )

    def handle(self, *args, **options):
        accounts = seed_chart_of_accounts()
        self.stdout.write(self.style.SUCCESS(f"Chart of accounts seeded: {accounts} accounts."))

        if options["backfill_member_savings"]:
            from accounts.models import SavingsAccount

            counter = 0
            for savings in SavingsAccount.objects.all().order_by("pk"):
                get_or_create_member_savings_account(savings)
                counter += 1
            self.stdout.write(self.style.SUCCESS(f"Backfilled member savings financial accounts: {counter}."))