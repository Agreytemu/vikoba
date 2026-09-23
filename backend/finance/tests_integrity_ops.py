"""Phase 5 STEP 11: integrity-monitor operational wiring tests.

The command must be alertable: a clean ledger exits 0, an anomaly exits 1
(both JSON and text modes), so a cron/CI wrapper can page on a non-zero code.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from finance.services.integrity import run_integrity_checks


class IntegrityCommandExitTests(TestCase):
    def test_clean_ledger_exits_zero(self):
        out = StringIO()
        call_command("financial_integrity", stdout=out)
        self.assertIn("No financial inconsistencies", out.getvalue())

    def test_anomaly_exits_nonzero_text_mode(self):
        from finance.models import FinancialTransaction

        FinancialTransaction.objects.create(
            reference="ORPHAN-TX-1",
            transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
            amount="1000.00",
            status=FinancialTransaction.Status.SUCCESS,
            description="no journal legs",
        )
        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command("financial_integrity", stdout=out)
        self.assertNotEqual(ctx.exception.code, 0)

    def test_anomaly_exits_nonzero_json_mode(self):
        from finance.models import FinancialTransaction

        FinancialTransaction.objects.create(
            reference="ORPHAN-TX-2",
            transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
            amount="1000.00",
            status=FinancialTransaction.Status.SUCCESS,
            description="no journal legs",
        )
        with self.assertRaises(SystemExit) as ctx:
            call_command("financial_integrity", "--json", stdout=StringIO())
        self.assertNotEqual(ctx.exception.code, 0)

    def test_report_shape_is_alertable(self):
        report = run_integrity_checks()
        self.assertIn("ok", report)
        self.assertIn("error_checks", report)
        for check in report["checks"].values():
            self.assertIn("status", check)
            self.assertIn("count", check)