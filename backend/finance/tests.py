"""Phase 1 finance tests: engine, balances, reversals, integration and API.

Covered behaviours:
- balanced double-entry enforced (unbalanced/zero/negative/unknown rejected)
- reference allocation format and uniqueness
- idempotency (same key / provider id never posts twice)
- status lifecycle (transition whitelist)
- reversal (original preserved, ledger re-balanced, cached balance sync)
- savings integration (post_savings_transaction journals every event)
- webhook defence-in-depth (no double credit even if upstream guard is bypassed)
- API authorization scoping (staff vs member)
"""
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from django.test import TestCase

from accounts.models import SavingsAccount, SavingsProduct, SavingsTransaction
from accounts.services import DuplicateSavingsPostError, post_savings_transaction
from finance.chart import CHART_OF_ACCOUNTS
from finance.models import AuditEvent, FinancialAccount, FinancialTransaction, JournalEntry
from finance.services.accounts_catalog import get_or_create_member_savings_account, get_org_account
from finance.services.balances import account_balance, savings_account_balance
from finance.services.engine import FinancialError, mark_status, post_transaction, reverse_transaction
from finance.services.reversals import reverse_financial_transaction
from groups.models import VikobaGroup
from members.models import Member

User = get_user_model()

REFERENCE_RE = re.compile(r"^[A-Z]+-\d{8}-\d{6}$")


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


class FinanceBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member1@test.com", username="member1", password="pass", is_active=True
        )
        self.user.role = User.MEMBER
        self.user.save()
        self.member = Member.objects.create(
            user=self.user,
            membership_number="MTEST001",
            first_name="Test",
            last_name="Member",
            phone_number="+255712345678",
            is_verified=True,
        )
        self.product = SavingsProduct.objects.create(name="Default", code="DEF", is_active=True)
        self.account = SavingsAccount.objects.create(
            member=self.member, product=self.product, balance=Decimal("0.00")
        )
        self.group = VikobaGroup.objects.create(
            name="TestGroup", area="Dar", country="Tanzania", created_by=self.member
        )
        self.group.memberships.create(member=self.member, role="member", shares_count=1)
        self.admin = User.objects.create_superuser(
            email="admin@test.com", username="admin", password="pass"
        )
        self.staff = User.objects.create_user(
            email="fin@test.com", username="fin", password="pass", is_active=True
        )
        self.staff.role = User.FINANCE
        self.staff.save()


class ChartOfAccountsTests(FinanceBase):
    def test_migration_seeds_chart(self):
        codes = set(
            FinancialAccount.objects.filter(
                member__isnull=True, group__isnull=True, savings_account__isnull=True
            ).values_list("account_number", flat=True)
        )
        self.assertEqual(len(codes), len(CHART_OF_ACCOUNTS))
        for account_no, _name, _atype, _desc in CHART_OF_ACCOUNTS:
            self.assertIn(account_no, codes)

    def test_seed_is_idempotent(self):
        from finance.chart import seed_chart_of_accounts

        before = FinancialAccount.objects.count()
        seed_chart_of_accounts()
        self.assertEqual(FinancialAccount.objects.count(), before)


class EnginePostTests(FinanceBase):
    def setUp(self):
        super().setUp()
        self.clearing = get_org_account("1100-CLEARING")
        self.savings = get_or_create_member_savings_account(self.account)

    def _deposit_entries(self, amount="10000.00"):
        return [
            {"account": self.clearing, "entry_type": "DEBIT", "amount": amount},
            {"account": self.savings, "entry_type": "CREDIT", "amount": amount},
        ]

    def test_posts_balanced_transaction(self):
        fin_tx, created = post_transaction(
            transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
            amount="10000.00",
            entries=self._deposit_entries("10000.00"),
            member=self.member,
            initiated_by=self.user,
        )
        self.assertTrue(created)
        self.assertEqual(fin_tx.status, FinancialTransaction.Status.SUCCESS)
        self.assertIsNotNone(fin_tx.posted_at)
        self.assertEqual(fin_tx.entries.count(), 2)
        self.assertEqual(
            sum(e.amount for e in fin_tx.entries.all()), _money("20000.00")
        )
        self.assertRegex(fin_tx.reference, REFERENCE_RE)
        self.assertTrue(fin_tx.reference.startswith("DEP-"))
        self.assertEqual(
            AuditEvent.objects.filter(transaction=fin_tx).count(), 2
        )  # created + posted

    def test_unbalanced_journal_rejected(self):
        with self.assertRaises(FinancialError) as ctx:
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                amount="10000.00",
                entries=[
                    {"account": self.clearing, "entry_type": "DEBIT", "amount": "12000.00"},
                    {"account": self.savings, "entry_type": "CREDIT", "amount": "10000.00"},
                ],
            )
        self.assertEqual(ctx.exception.code, FinancialError.UNBALANCED_JOURNAL)
        self.assertEqual(FinancialTransaction.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_zero_and_negative_amounts_rejected(self):
        for amount, code in (("0", FinancialError.ZERO_AMOUNT), ("-5", FinancialError.NEGATIVE_AMOUNT)):
            with self.assertRaises(FinancialError) as ctx:
                post_transaction(
                    transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                    amount=amount,
                    entries=self._deposit_entries("100.00"),
                )
            self.assertEqual(ctx.exception.code, code)

    def test_missing_or_unknown_account_rejected(self):
        with self.assertRaises(FinancialError) as ctx:
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                amount="100.00",
                entries=[
                    {"account": "9999-MISSING", "entry_type": "DEBIT", "amount": "100.00"},
                    {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
                ],
            )
        self.assertEqual(ctx.exception.code, FinancialError.ACCOUNT_NOT_FOUND)

    def test_negative_entry_amount_rejected(self):
        with self.assertRaises(FinancialError) as ctx:
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                amount="100.00",
                entries=[
                    {"account": self.clearing, "entry_type": "DEBIT", "amount": "-100.00"},
                    {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
                ],
            )
        self.assertEqual(ctx.exception.code, FinancialError.NEGATIVE_AMOUNT)

    def test_entry_without_debit_rejected(self):
        with self.assertRaises(FinancialError) as ctx:
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                amount="100.00",
                entries=[
                    {"account": self.clearing, "entry_type": "CREDIT", "amount": "100.00"},
                    {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
                ],
            )
        self.assertEqual(ctx.exception.code, FinancialError.UNBALANCED_JOURNAL)

    def test_currency_mismatch_rejected(self):
        with self.assertRaises(FinancialError) as ctx:
            post_transaction(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                amount="100.00",
                currency="TZS",
                entries=[
                    {"account": self.clearing, "entry_type": "DEBIT", "amount": "100.00", "currency": "USD"},
                    {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
                ],
            )
        self.assertEqual(ctx.exception.code, FinancialError.CURRENCY_MISMATCH)

    def test_duplicate_reference_is_idempotent(self):
        first, created = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            reference="DEP-TEST-000001",
            entries=self._deposit_entries("100.00"),
        )
        self.assertTrue(created)
        # An explicit duplicate reference collides with a posted transaction and
        # returns the existing record instead of posting again.
        second, created_again = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            reference="DEP-TEST-000001",
            entries=self._deposit_entries("100.00"),
        )
        self.assertFalse(created_again)
        self.assertEqual(first.reference, second.reference)
        self.assertEqual(FinancialTransaction.objects.filter(reference="DEP-TEST-000001").count(), 1)

    def test_idempotency_key_prevents_second_post(self):
        first, created = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            entries=self._deposit_entries("100.00"),
            idempotency_key="dup-key-1",
        )
        self.assertTrue(created)
        second, created_again = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            entries=self._deposit_entries("100.00"),
            idempotency_key="dup-key-1",
        )
        self.assertFalse(created_again)
        self.assertEqual(first.reference, second.reference)
        self.assertEqual(FinancialTransaction.objects.count(), 1)

    def test_reference_allocation_is_monotonic(self):
        refs = []
        for i in range(5):
            tx, _ = post_transaction(
                transaction_type="DEPOSIT",
                amount="10.00",
                entries=self._deposit_entries("10.00"),
            )
            refs.append(tx.reference)
        self.assertEqual(len(set(refs)), 5)
        self.assertEqual(refs[0][-6:], "000001")
        self.assertEqual(refs[-1][-6:], "000005")


class EngineStatusTests(FinanceBase):
    def setUp(self):
        super().setUp()
        self.tx, _ = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            currency="TZS",
            entries=[
                {"account": get_org_account("1100-CLEARING"), "entry_type": "DEBIT", "amount": "100.00"},
                {"account": get_or_create_member_savings_account(self.account), "entry_type": "CREDIT", "amount": "100.00"},
            ],
            status="PENDING",
        )

    def test_valid_pending_to_success_transition(self):
        mark_status(self.tx, "SUCCESS")
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "SUCCESS")
        self.assertIsNotNone(self.tx.posted_at)

    def test_invalid_success_to_failed_transition(self):
        mark_status(self.tx, "SUCCESS")
        with self.assertRaises(FinancialError) as ctx:
            mark_status(self.tx, "FAILED")
        self.assertEqual(ctx.exception.code, FinancialError.INVALID_STATUS_TRANSITION)

    def test_terminal_transition_rejected(self):
        mark_status(self.tx, "CANCELLED")
        with self.assertRaises(FinancialError) as ctx:
            mark_status(self.tx, "PENDING")
        self.assertEqual(ctx.exception.code, FinancialError.INVALID_STATUS_TRANSITION)


class ReversalTests(FinanceBase):
    def setUp(self):
        super().setUp()
        self.clearing = get_org_account("1100-CLEARING")
        self.savings = get_or_create_member_savings_account(self.account)

    def test_reversal_keeps_original_and_rebalances(self):
        deposit, _ = post_transaction(
            transaction_type="DEPOSIT",
            amount="50000.00",
            entries=[
                {"account": self.clearing, "entry_type": "DEBIT", "amount": "50000.00"},
                {"account": self.savings, "entry_type": "CREDIT", "amount": "50000.00"},
            ],
        )
        reversal = reverse_transaction(deposit, reason="wrong amount", initiated_by=self.staff)

        deposit.refresh_from_db()
        self.assertEqual(deposit.status, FinancialTransaction.Status.REVERSED)
        self.assertEqual(deposit.reversal_reason, "wrong amount")

        reversal.refresh_from_db()
        self.assertEqual(reversal.transaction_type, FinancialTransaction.TransactionType.REVERSAL)
        self.assertEqual(reversal.status, FinancialTransaction.Status.SUCCESS)
        self.assertEqual(reversal.reversal_of_id, deposit.pk)
        self.assertEqual(reversal.amount, deposit.amount)
        self.assertEqual(reversal.entries.count(), 2)

        # Ledger must net back to zero.
        self.assertEqual(account_balance(self.clearing), Decimal("0.00"))
        self.assertEqual(account_balance(self.savings), Decimal("0.00"))

        # The reversal journal is the exact opposite of the original.
        original_dr = set(
            (e.account_id, e.entry_type) for e in deposit.entries.all()
        )
        reversal_dr = set(
            (e.account_id, e.entry_type) for e in reversal.entries.all()
        )
        for (account_id, entry_type) in original_dr:
            self.assertIn(
                (account_id, "CREDIT" if entry_type == "DEBIT" else "DEBIT"),
                reversal_dr,
            )

    def test_double_reversal_rejected(self):
        deposit, _ = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            entries=[
                {"account": self.clearing, "entry_type": "DEBIT", "amount": "100.00"},
                {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
            ],
        )
        reverse_transaction(deposit, reason="first")
        with self.assertRaises(FinancialError) as ctx:
            reverse_transaction(deposit, reason="second")
        self.assertEqual(ctx.exception.code, FinancialError.ALREADY_REVERSED)

    def test_reversal_of_failed_transaction_rejected(self):
        tx, _ = post_transaction(
            transaction_type="DEPOSIT",
            amount="100.00",
            entries=[
                {"account": self.clearing, "entry_type": "DEBIT", "amount": "100.00"},
                {"account": self.savings, "entry_type": "CREDIT", "amount": "100.00"},
            ],
            status="FAILED",
        )
        with self.assertRaises(FinancialError) as ctx:
            reverse_transaction(tx, reason="nope")
        self.assertEqual(ctx.exception.code, FinancialError.INVALID_STATUS_TRANSITION)


class BalanceServiceTests(FinanceBase):
    def test_balances_after_deposit_and_withdrawal(self):
        savings_ledger = get_or_create_member_savings_account(self.account)
        clearing = get_org_account("1100-CLEARING")
        self.assertEqual(account_balance(savings_ledger), Decimal("0.00"))
        self.assertEqual(account_balance(clearing), Decimal("0.00"))

        post_transaction(
            transaction_type="DEPOSIT",
            amount="1000.00",
            entries=[
                {"account": clearing, "entry_type": "DEBIT", "amount": "1000.00"},
                {"account": savings_ledger, "entry_type": "CREDIT", "amount": "1000.00"},
            ],
        )
        self.assertEqual(account_balance(savings_ledger), Decimal("1000.00"))
        self.assertEqual(account_balance(clearing), Decimal("1000.00"))

        post_transaction(
            transaction_type="WITHDRAWAL",
            amount="400.00",
            entries=[
                {"account": savings_ledger, "entry_type": "DEBIT", "amount": "400.00"},
                {"account": clearing, "entry_type": "CREDIT", "amount": "400.00"},
            ],
        )
        self.assertEqual(account_balance(savings_ledger), Decimal("600.00"))
        self.assertEqual(account_balance(clearing), Decimal("600.00"))

    def test_savings_ledger_balance_matches_cached(self):
        post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("25000.00"),
            user=self.admin,
            narration="test deposit",
        )
        self.account.refresh_from_db()
        self.assertEqual(savings_account_balance(self.account), self.account.balance)
        self.assertEqual(self.account.balance, Decimal("25000.00"))

    def test_precision_kept_to_cents(self):
        self.assertEqual(_money("10.999"), Decimal("11.00"))
        _money_quantized = post_transaction(
            transaction_type="DEPOSIT",
            amount="10.999",
            entries=[
                {"account": get_org_account("1100-CLEARING"), "entry_type": "DEBIT", "amount": "10.999"},
                {"account": get_or_create_member_savings_account(self.account), "entry_type": "CREDIT", "amount": "10.999"},
            ],
        )[0]
        self.assertEqual(_money_quantized.amount, Decimal("11.00"))


class SavingsIntegrationTests(FinanceBase):
    def test_deposit_journals_and_tracks_savings_link(self):
        fin_tx = SavingsTransaction.objects.count()
        txn = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("10000.00"),
            user=self.admin,
            narration="cash deposit",
            group=self.group,
        )
        self.assertEqual(SavingsTransaction.objects.count(), fin_tx + 1)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("10000.00"))

        finance_tx = FinancialTransaction.objects.filter(
            savings_transaction=txn
        ).first()
        self.assertIsNotNone(finance_tx)
        self.assertEqual(finance_tx.transaction_type, "DEPOSIT")
        self.assertEqual(finance_tx.group, self.group)  # group passed through
        self.assertEqual(finance_tx.amount, Decimal("10000.00"))
        self.assertEqual(finance_tx.entries.count(), 2)

        ms = get_or_create_member_savings_account(self.account)
        self.assertEqual(account_balance(ms), Decimal("10000.00"))

    def test_deposit_scope_group(self):
        txn = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("5000.00"),
            user=self.admin,
            group=self.group,
        )
        finance_tx = FinancialTransaction.objects.get(savings_transaction=txn)
        self.assertEqual(finance_tx.group, self.group)
        self.assertEqual(finance_tx.member, self.member)

    def test_withdrawal_journals_opposite_direction(self):
        post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("10000.00"),
            user=self.admin,
        )
        txn = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.WITHDRAWAL,
            amount=Decimal("2500.00"),
            user=self.admin,
        )
        finance_tx = FinancialTransaction.objects.get(savings_transaction=txn)
        self.assertEqual(finance_tx.transaction_type, "WITHDRAWAL")
        ms = get_or_create_member_savings_account(self.account)
        self.assertEqual(account_balance(ms), Decimal("7500.00"))
        self.assertEqual(account_balance(get_org_account("1100-CLEARING")), Decimal("7500.00"))

    def test_interest_journals_to_interest_expense(self):
        txn = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.INTEREST,
            amount=Decimal("800.00"),
            user=self.admin,
        )
        finance_tx = FinancialTransaction.objects.get(savings_transaction=txn)
        expense_legs = finance_tx.entries.filter(
            account_id=get_org_account("5004-INTEREST_EXPENSE").pk
        )
        self.assertEqual(expense_legs.count(), 1)
        self.assertEqual(expense_legs.first().entry_type, JournalEntry.DEBIT)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("800.00"))

    def test_idempotency_key_blocks_duplicate_savings_post(self):
        key = "sav-dep-dup-1"
        first = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("4000.00"),
            user=self.admin,
            idempotency_key=key,
        )
        self.account.refresh_from_db()
        balance_after_first = self.account.balance

        with self.assertRaises(DuplicateSavingsPostError):
            post_savings_transaction(
                account=self.account,
                transaction_type=SavingsTransaction.DEPOSIT,
                amount=Decimal("4000.00"),
                user=self.admin,
                idempotency_key=key,
            )
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, balance_after_first)
        self.assertEqual(
            SavingsTransaction.objects.filter(pk=first.pk).count(), 1
        )
        self.assertEqual(FinancialTransaction.objects.filter(idempotency_key=key).count(), 1)

    def test_reversal_syncs_cached_savings_balance(self):
        txn = post_savings_transaction(
            account=self.account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("30000.00"),
            user=self.admin,
        )
        finance_tx = FinancialTransaction.objects.get(savings_transaction=txn)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("30000.00"))

        reverse_financial_transaction(
            fin_tx=finance_tx,
            reason="duplicate deposit",
            actor=self.staff,
        )

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("0.00"))
        finance_tx.refresh_from_db()
        self.assertEqual(finance_tx.status, FinancialTransaction.Status.REVERSED)


class WebhookIntegrationTests(FinanceBase):
    """Defence-in-depth: the webhook ledger helpers journal once and only once."""

    def setUp(self):
        super().setUp()
        self.payment_service = __import__(
            "payments.services.payment_service",
            fromlist=["handle_payment_completed", "initiate_contribution_payment"],
        )

    def test_contribution_webhook_posts_financial_transaction(self):
        from payments.models import WebhookEvent

        pay_tx = self.payment_service.initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal("50000"),
            month="2026-01",
        )
        event = WebhookEvent.objects.create(
            event_id="evt_fin_001",
            event_type="payment.completed",
            payload={
                "reference": pay_tx.provider_reference,
                "amount": {"value": 50000, "currency": "TZS"},
                "settlement": {"gross": 50000, "fees": 0, "net": 50000},
                "channel": {"type": "mobile"},
            },
        )
        self.payment_service.handle_payment_completed(event, event.payload)

        fin_tx = FinancialTransaction.objects.filter(payment_transaction=pay_tx).first()
        self.assertIsNotNone(fin_tx)
        self.assertEqual(fin_tx.transaction_type, "CONTRIBUTION")
        self.assertEqual(fin_tx.amount, Decimal("50000.00"))
        self.assertEqual(fin_tx.member, self.member)
        self.assertEqual(fin_tx.group, self.group)
        self.assertIsNotNone(fin_tx.savings_transaction)
        ms = get_or_create_member_savings_account(self.account)
        self.assertEqual(account_balance(ms), Decimal("50000.00"))

    def test_duplicate_webhook_delivery_no_double_journal(self):
        from payments.models import WebhookEvent

        pay_tx = self.payment_service.initiate_contribution_payment(
            member=self.member,
            group=self.group,
            amount=Decimal("30000"),
            month="2026-02",
        )
        payload = {
            "reference": pay_tx.provider_reference,
            "amount": {"value": 30000, "currency": "TZS"},
            "settlement": {"gross": 30000, "fees": 0, "net": 30000},
            "channel": {"type": "mobile"},
        }
        event = WebhookEvent.objects.create(
            event_id="evt_fin_002",
            event_type="payment.completed",
            payload=payload,
        )

        self.payment_service.handle_payment_completed(event, payload)
        self.payment_service.handle_payment_completed(event, payload)

        self.assertEqual(FinancialTransaction.objects.filter(payment_transaction=pay_tx).count(), 1)
        ms = get_or_create_member_savings_account(self.account)
        self.assertEqual(account_balance(ms), Decimal("30000.00"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("30000.00"))


class FinanceAPITests(FinanceBase):
    def setUp(self):
        super().setUp()
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(user=self.staff)
        self.member_client = APIClient()
        self.member_client.force_authenticate(user=self.user)

    def _post(self, amount="10000.00"):
        return post_transaction(
            transaction_type="DEPOSIT",
            amount=amount,
            member=self.member,
            entries=[
                {"account": get_org_account("1100-CLEARING"), "entry_type": "DEBIT", "amount": amount},
                {"account": get_or_create_member_savings_account(self.account), "entry_type": "CREDIT", "amount": amount},
            ],
        )[0]

    def test_staff_lists_accounts(self):
        resp = self.staff_client.get("/api/v1/finance/accounts/")
        self.assertEqual(resp.status_code, 200)
        codes = [a["account_number"] for a in resp.json()]
        self.assertIn("1100-CLEARING", codes)

    def test_staff_lists_transactions(self):
        self._post()
        resp = self.staff_client.get("/api/v1/finance/transactions/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_transaction_retrieve_by_reference(self):
        tx = self._post()
        resp = self.staff_client.get(f"/api/v1/finance/transactions/{tx.reference}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["reference"], tx.reference)
        self.assertEqual(len(data["entries"]), 2)

    def test_member_sees_only_their_own_transactions(self):
        other_member = Member.objects.create(
            user=User.objects.create_user(email="m2@test.com", username="m2", password="pass", is_active=True),
            membership_number="MTEST002",
            first_name="Other",
            phone_number="+255700000000",
        )
        self._post("5000.00")
        other_account = SavingsAccount.objects.create(
            member=other_member, product=self.product, balance=Decimal("0.00")
        )
        post_savings_transaction(
            account=other_account,
            transaction_type=SavingsTransaction.DEPOSIT,
            amount=Decimal("9000.00"),
            user=self.admin,
        )
        resp = self.member_client.get("/api/v1/finance/me/")
        self.assertEqual(resp.status_code, 200)
        refs = [t["reference"] for t in resp.json()]
        self.assertEqual(len(refs), 1)
        self.assertIn("DEP-", refs[0])
        # the other member's deposit must not appear
        for t in resp.json():
            self.assertEqual(str(t["member"]), str(self.member.pk))

    def test_member_cannot_list_accounts(self):
        resp = self.member_client.get("/api/v1/finance/accounts/")
        self.assertEqual(resp.status_code, 403)

    def test_member_cannot_reverse(self):
        tx = self._post()
        resp = self.member_client.post(
            f"/api/v1/finance/transactions/{tx.reference}/reverse/",
            {"reason": "nope"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        tx.refresh_from_db()
        self.assertEqual(tx.status, FinancialTransaction.Status.SUCCESS)

    def test_staff_can_reverse_via_api(self):
        savings = get_or_create_member_savings_account(self.account)
        self.assertEqual(account_balance(savings), Decimal("0.00"))
        tx = self._post("20000.00")
        self.assertEqual(account_balance(savings), Decimal("20000.00"))
        resp = self.staff_client.post(
            f"/api/v1/finance/transactions/{tx.reference}/reverse/",
            {"reason": "operator correction"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["transaction_type"], "REVERSAL")
        tx.refresh_from_db()
        self.assertEqual(tx.status, FinancialTransaction.Status.REVERSED)
        self.assertEqual(account_balance(savings), Decimal("0.00"))

    def test_staff_journal_create(self):
        resp = self.staff_client.post(
            "/api/v1/finance/journal/",
            {
                "transaction_type": "ADJUSTMENT",
                "amount": "500.00",
                "description": "manual correction",
                "entries": [
                    {"account": "1100-CLEARING", "entry_type": "DEBIT", "amount": "500.00"},
                    {"account": "2001-MEMBER_SAVINGS", "entry_type": "CREDIT", "amount": "500.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(FinancialTransaction.objects.count(), 1)
        self.assertEqual(resp.json()["status"], "SUCCESS")

    def test_staff_journal_unbalanced_rejected(self):
        resp = self.staff_client.post(
            "/api/v1/finance/journal/",
            {
                "transaction_type": "ADJUSTMENT",
                "amount": "500.00",
                "entries": [
                    {"account": "1100-CLEARING", "entry_type": "DEBIT", "amount": "600.00"},
                    {"account": "2001-MEMBER_SAVINGS", "entry_type": "CREDIT", "amount": "500.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], FinancialError.UNBALANCED_JOURNAL)
        self.assertEqual(FinancialTransaction.objects.count(), 0)

    def test_member_journal_rejected(self):
        resp = self.member_client.post(
            "/api/v1/finance/journal/",
            {
                "transaction_type": "ADJUSTMENT",
                "amount": "500.00",
                "entries": [
                    {"account": "1100-CLEARING", "entry_type": "DEBIT", "amount": "500.00"},
                    {"account": "2001-MEMBER_SAVINGS", "entry_type": "CREDIT", "amount": "500.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)