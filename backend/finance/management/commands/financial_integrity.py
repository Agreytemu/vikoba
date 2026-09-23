import json

from django.core.management.base import BaseCommand

from finance.services.integrity import run_integrity_checks


class Command(BaseCommand):
    """Run the on-demand financial integrity checks.

    Reports unbalanced journals, journal-less transactions, settled payments
    without a ledger posting, cached-vs-ledger drift for savings and loan
    principal, and duplicate provider references. Read-only — nothing is
    amended or "fixed". Safe to run any time; intended for the ops dashboard
    and after important financial events.
    """

    help = "Verify books still tie to the double-entry journal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", action="store_true", help="Print the full report as JSON."
        )

    def handle(self, *args, **options):
        report = run_integrity_checks()

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, default=str))
            if not report["ok"]:
                raise SystemExit(1)
            return

        self.stdout.write(self.style.HTTP_INFO(f"Integrity run at {report['run_at']}:"))
        for name, check in report["checks"].items():
            if check["status"] == "ok":
                mark = self.style.SUCCESS("OK    ")
            elif check["status"] == "warning":
                mark = self.style.WARNING("WARN  ")
            else:
                mark = self.style.ERROR("ERROR ")
            self.stdout.write(f"{mark} {name:<32} count={check['count']}")
            for sample in check["samples"][:3]:
                self.stdout.write(f"      - {sample}")

        if report["ok"]:
            self.stdout.write(self.style.SUCCESS("No financial inconsistencies flagged."))
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Flagged error checks: {', '.join(report['error_checks'])} — "
                    "investigate before treating figures as authoritative."
                )
            )
            raise SystemExit(1)