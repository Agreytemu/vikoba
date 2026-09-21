"""Apply overdue penalties to active loans and optionally classify defaults.

Run regularly (e.g. nightly cron):

    python manage.py process_loan_overdues

All penalty charges are idempotent per (loan, installment) — re-running never
double-charges. Automatic DEFAULTED classification is OFF unless
``LOAN_DEFAULT_THRESHOLD_DAYS`` is configured in settings.
"""

from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from loans.models import LoanAccount
from loans.penalties import process_overdue_loans


class Command(BaseCommand):
    help = "Apply overdue loan penalties and auto-classify defaults (when enabled)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            type=str,
            default=None,
            help="ISO date to evaluate overdues as of (defaults to today).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without persisting anything.",
        )

    def handle(self, *args, **options):
        as_of_raw = options["as_of"]
        if as_of_raw:
            as_of = datetime.strptime(as_of_raw, "%Y-%m-%d").date()
        else:
            as_of = timezone.now().date()

        charged = process_overdue_loans(as_of=as_of)
        for loan, installment, penalty in charged:
            self.stdout.write(
                f"penalty {penalty.amount} on {loan.loan_number} "
                f"installment {installment.installment_number} ({penalty.reason})"
            )
        self.stdout.write(self.style.SUCCESS(f"{len(charged)} penalty(ies) applied."))

        threshold_raw = getattr(settings, "LOAN_DEFAULT_THRESHOLD_DAYS", None)
        if not threshold_raw:
            self.stdout.write("DEFAULTED auto-classification is disabled (LOAN_DEFAULT_THRESHOLD_DAYS unset).")
            return

        threshold = int(threshold_raw)
        cutoff = as_of - timedelta(days=threshold)
        queryset = LoanAccount.objects.filter(
            status=LoanAccount.DISBURSED,
            disbursed_at__lt=datetime.combine(cutoff, datetime.min.time(), tzinfo=timezone.get_current_timezone()),
            outstanding_principal__gt=0,
        )
        classified = []
        for loan in queryset:
            if options["dry_run"]:
                self.stdout.write(f"would classify {loan.loan_number} as DEFAULTED")
                continue
            loan.status = LoanAccount.DEFAULTED
            loan.save(update_fields=["status"])
            classified.append(loan.loan_number)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"{queryset.count()} loan(s) flagged for automatic defaulting."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{len(classified)} loan(s) classified DEFAULTED."))