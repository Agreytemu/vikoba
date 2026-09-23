"""Phase 3 loan & credit engine tests (spec §37).

Covers the backend-authoritative gates: approval hard checks, approved_amount
snapshotting, per-group policy + group capacity locks, penalty idempotency with
a keyed journal, per-installment repayment allocation (including partial
payments and penalty-first settlement), loan completion, and the member balance
endpoint.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct
from finance.models import AuditEvent, FinancialTransaction
from groups.models import GroupMembership, VikobaGroup
from kyc.models import KYCProfile
from kyc.statuses import KYCLevel, KYCStatus, KYCVerificationMethod
from members.models import Member
from users.models import User

from .eligibility import check_eligibility
from .models import (
    GroupLoanPolicy,
    LoanAccount,
    LoanApplication,
    LoanPenalty,
    LoanProduct,
    LoanSchedule,
    LoanTransaction,
)
from .penalties import charge_penalty, process_overdue_loans
from .repayments import post_repayment
from .services import (
    approve_application,
    disburse_application,
    post_installment_repayment,
)


def _make_user(email, username, role, **kwargs):
    return User.objects.create_user(
        email=email,
        username=username,
        password="test-password-123",
        role=role,
        **kwargs,
    )


def _make_member(user=None, number=None):
    member = Member.objects.create(
        user=user,
        first_name="Phase",
        last_name=number or "Three",
        phone_number=f"+2557{number or '0000000'}",
        email=(user.email if user else "phase@example.com"),
        date_of_birth="1990-01-01",
        kra_pin=f"P{number or '00000'}ABC",
        country="Tanzania",
    )
    member.is_verified = True
    member.save(update_fields=["is_verified"])
    KYCProfile.objects.create(
        member=member,
        status=KYCStatus.VERIFIED,
        verification_level=KYCLevel.LEVEL_1,
        verification_method=KYCVerificationMethod.PROVIDER,
        provider="simulated",
        provider_reference="SIM-KYC-TESTP3",
    )
    return member


def _make_product(requires_guarantors=False):
    return LoanProduct.objects.create(
        name="Phase3 Loan",
        interest_rate=Decimal("12.00"),
        repayment_period_months=12,
        multiplier=Decimal("3.00"),
        min_amount=Decimal("1000.00"),
        max_amount=Decimal("500000.00"),
        max_term_months=24,
        requires_guarantors=requires_guarantors,
        interest_type=LoanProduct.FLAT,
        is_active=True,
    )


class ApprovalGateTests(TestCase):
    def setUp(self):
        self.officer = _make_user("p3loan@example.com", "p3loan", User.LOAN)
        self.member = _make_member(number="1001")
        self.product = _make_product()
        self.savings = SavingsProduct.objects.create(
            name="P3 Savings", code="P3S", minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"), withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )
        SavingsAccount.objects.create(member=self.member, product=self.savings, balance=Decimal("100000.00"))

    def _under_review(self, amount="120000.00", months=12):
        app = LoanApplication.objects.create(
            member=self.member,
            loan_type=self.product,
            requested_amount=Decimal(amount),
            purpose="Phase3 test",
            repayment_period_months=months,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            created_by=self.officer,
            status=LoanApplication.Status.UNDER_REVIEW,
        )
        return app

    def test_approve_blocks_below_minimum(self):
        app = self._under_review(amount="500.00")
        with self.assertRaises(ValueError) as ctx:
            approve_application(application=app, user=self.officer)
        self.assertIn("below the minimum", str(ctx.exception))

    def test_approve_blocks_above_effective_max(self):
        app = self._under_review(amount="600000.00")
        with self.assertRaises(ValueError) as ctx:
            approve_application(application=app, user=self.officer)
        self.assertIn("exceeds the maximum", str(ctx.exception))

    def test_approve_blocks_term_over_max(self):
        app = self._under_review(amount="120000.00", months=36)
        with self.assertRaises(ValueError) as ctx:
            approve_application(application=app, user=self.officer)
        self.assertIn("exceeds the maximum", str(ctx.exception))

    def test_approve_blocks_when_existing_active_loan_pending(self):
        first = self._under_review(amount="50000.00")
        approve_application(application=first, user=self.officer)
        second = self._under_review(amount="50000.00")
        ok, errors = check_eligibility(second)
        self.assertFalse(ok)
        self.assertTrue(any("awaiting disbursement" in error for error in errors))
        with self.assertRaises(ValueError):
            approve_application(application=second, user=self.officer)

    def test_approve_snapshots_approved_amount_and_audits(self):
        app = self._under_review(amount="120000.00")
        result = approve_application(
            application=app, user=self.officer, approved_amount=Decimal("110000.00"), notes="Board agreed less."
        )
        self.assertEqual(result.approved_amount, Decimal("110000.00"))
        self.assertEqual(result.status, LoanApplication.Status.APPROVED)
        event = AuditEvent.objects.get(action="loan.application.approved", reference=app.application_number)
        self.assertEqual(event.metadata.get("approved_amount"), "110000.00")
        self.assertEqual(event.user, self.officer)

    def test_approve_requires_under_review(self):
        app = LoanApplication.objects.create(
            member=self.member,
            loan_type=self.product,
            requested_amount=Decimal("120000.00"),
            purpose="Phase3 test",
            repayment_period_months=12,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            created_by=self.officer,
            status=LoanApplication.Status.SUBMITTED,
        )
        with self.assertRaises(ValueError):
            approve_application(application=app, user=self.officer)


class GroupCapacityTests(TestCase):
    def setUp(self):
        self.officer = _make_user("p3group@example.com", "p3group", User.LOAN)
        self.product = _make_product()
        self.savings = SavingsProduct.objects.create(
            name="P3 Savings", code="P3S", minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"), withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )
        self.group = VikobaGroup.objects.create(
            name="Kitega SACCO", status=VikobaGroup.Status.ACTIVE, created_by=_make_member(number="2099"),
        )
        self.member_a = _make_member(number="2001")
        self.member_b = _make_member(number="2002")
        GroupMembership.objects.create(group=self.group, member=self.member_a, role=GroupMembership.Role.MEMBER, is_active=True)
        GroupMembership.objects.create(group=self.group, member=self.member_b, role=GroupMembership.Role.MEMBER, is_active=True)
        SavingsAccount.objects.create(member=self.member_a, product=self.savings, balance=Decimal("100000.00"))
        SavingsAccount.objects.create(member=self.member_b, product=self.savings, balance=Decimal("100000.00"))
        GroupLoanPolicy.objects.create(
            group=self.group,
            max_amount=None,
            max_term_months=None,
            multiplier=None,
            interest_rate=None,
            interest_type=None,
            requires_guarantors=None,
            penalty_rate=None,
            penalty_grace_days=None,
            group_capacity_enabled=True,
            updated_by=self.officer,
            updated_at=timezone.now(),
        )

    def _under_review(self, member, amount, months=12):
        return LoanApplication.objects.create(
            member=member,
            loan_type=self.product,
            requested_amount=Decimal(amount),
            purpose="Group loan",
            repayment_period_months=months,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            group=self.group,
            created_by=self.officer,
            status=LoanApplication.Status.UNDER_REVIEW,
        )

    def test_group_capacity_limits_concurrent_approvals(self):
        first = self._under_review(self.member_a, "80000.00")
        approve_application(application=first, user=self.officer)
        # remaining capacity = 200000 savings - 80000 approved = 120000
        within = self._under_review(self.member_b, "120000.00")
        approve_application(application=within, user=self.officer)
        beyond = self._under_review(self.member_b, "120000.01")
        ok, errors = check_eligibility(beyond)
        self.assertFalse(ok)
        self.assertTrue(any("lending capacity" in error for error in errors))
        with self.assertRaises(ValueError):
            approve_application(application=beyond, user=self.officer)

    def test_group_policy_overrides_product_maximum(self):
        GroupLoanPolicy.objects.filter(group=self.group).update(max_amount=Decimal("60000.00"))
        app = self._under_review(self.member_a, "80000.00")
        with self.assertRaises(ValueError) as ctx:
            approve_application(application=app, user=self.officer)
        self.assertIn("exceeds the maximum", str(ctx.exception))


class PenaltyTests(TestCase):
    def setUp(self):
        self.officer = _make_user("p3pen@example.com", "p3pen", User.LOAN)
        self.member = _make_member(number="3001")
        self.product = _make_product()
        self.loan = LoanAccount.objects.create(
            member=self.member,
            product=self.product,
            principal_amount=Decimal("100000.00"),
            interest_rate=Decimal("12.00"),
            interest_type=LoanProduct.FLAT,
            term_months=3,
            status=LoanAccount.DISBURSED,
            disbursed_at=timezone.now(),
            outstanding_principal=Decimal("100000.00"),
            outstanding_interest=Decimal("3000.00"),
            outstanding_penalty=Decimal("0.00"),
            penalty_rate=Decimal("5.00"),
            created_by=self.officer,
        )
        self.installment = LoanSchedule.objects.create(
            loan=self.loan,
            installment_number=1,
            due_date=timezone.now().date() - timedelta(days=30),
            principal_due=Decimal("33333.34"),
            interest_due=Decimal("1000.00"),
            total_due=Decimal("34333.34"),
        )

    @override_settings(LOAN_PENALTY_RATE="5.00", LOAN_PENALTY_GRACE_DAYS=0)
    def test_penalty_charging_is_idempotent_per_installment(self):
        first = charge_penalty(loan=self.loan, installment=self.installment, as_of=timezone.now().date())
        second = charge_penalty(loan=self.loan, installment=self.installment, as_of=timezone.now().date())
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LoanPenalty.objects.count(), 1)
        self.assertEqual(first.amount, Decimal("1666.67"))  # 5% of principal_due
        penalty = LoanPenalty.objects.get(pk=first.pk)
        self.assertEqual(penalty.amount_paid, Decimal("0.00"))
        self.assertEqual(penalty.status, LoanPenalty.Status.OPEN)
        self.assertEqual(
            FinancialTransaction.objects.filter(
                idempotency_key=f"penalty-{self.loan.loan_number}-1"
            ).count(),
            1,
        )
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.outstanding_penalty, Decimal("1666.67"))

    @override_settings(LOAN_PENALTY_RATE="5.00", LOAN_PENALTY_GRACE_DAYS=0)
    def test_process_overdue_loans_charges_only_within_grace_window(self):
        charged = process_overdue_loans(as_of=timezone.now().date())
        self.assertEqual(len(charged), 1)
        second_run = process_overdue_loans(as_of=timezone.now().date())
        self.assertEqual(len(second_run), 0)
        self.assertEqual(LoanPenalty.objects.count(), 1)

    @override_settings(LOAN_PENALTY_RATE="5.00", LOAN_PENALTY_GRACE_DAYS=7)
    def test_penalty_within_grace_window_is_not_charged(self):
        self.installment.due_date = timezone.now().date() - timedelta(days=3)
        self.installment.save(update_fields=["due_date"])
        penalty = charge_penalty(loan=self.loan, installment=self.installment)
        self.assertIsNone(penalty)


class RepaymentAllocationTests(TestCase):
    def setUp(self):
        self.officer = _make_user("p3repay@example.com", "p3repay", User.LOAN)
        self.member = _make_member(number="4001")
        self.savings = SavingsProduct.objects.create(
            name="P3 Savings", code="P3S", minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"), withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )
        SavinsgAccount = SavingsAccount.objects.create(member=self.member, product=self.savings, balance=Decimal("100000.00"))
        self.account = SavinsgAccount
        self.product = _make_product()
        self.loan = LoanAccount.objects.create(
            member=self.member,
            product=self.product,
            principal_amount=Decimal("16000.00"),
            interest_rate=Decimal("12.00"),
            interest_type=LoanProduct.FLAT,
            term_months=2,
            status=LoanAccount.DISBURSED,
            disbursed_at=timezone.now(),
            outstanding_principal=Decimal("16000.00"),
            outstanding_interest=Decimal("4000.00"),
            outstanding_penalty=Decimal("0.00"),
            penalty_rate=Decimal("5.00"),
            created_by=self.officer,
        )
        self.schedule = [
            LoanSchedule.objects.create(
                loan=self.loan, installment_number=n,
                due_date=timezone.now().date() + timedelta(days=30 * n),
                principal_due=Decimal("8000.00"), interest_due=Decimal("2000.00"),
                total_due=Decimal("10000.00"),
            )
            for n in (1, 2)
        ]

    def test_partial_repayment_allocates_interest_then_principal(self):
        loan_tx, allocation = post_repayment(loan=self.loan, amount=Decimal("5000.00"), user=self.officer)
        self.assertEqual(allocation["interest_paid"], Decimal("2000.00"))
        self.assertEqual(allocation["principal_paid"], Decimal("3000.00"))
        self.assertEqual(allocation["penalty_paid"], Decimal("0.00"))
        self.schedule[0].refresh_from_db()
        self.assertFalse(self.schedule[0].is_paid)
        self.assertEqual(self.schedule[0].partially_paid_amount, Decimal("5000.00"))
        self.assertEqual(self.schedule[0].status, LoanSchedule.Status.PARTIALLY_PAID)
        self.assertEqual(self.schedule[0].outstanding_due, Decimal("5000.00"))
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.outstanding_principal, Decimal("13000.00"))
        self.assertEqual(self.loan.outstanding_interest, Decimal("2000.00"))

    def test_partial_then_completion_closes_the_loan(self):
        post_repayment(loan=self.loan, amount=Decimal("5000.00"), user=self.officer)
        # completes installment 1 (5000 + 5000 principal-only), leftover 2000
        # covers installment 2's entire interest leg.
        post_repayment(loan=self.loan, amount=Decimal("7000.00"), user=self.officer)
        self.schedule[0].refresh_from_db()
        self.assertTrue(self.schedule[0].is_paid)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.outstanding_principal, Decimal("8000.00"))
        self.assertEqual(self.loan.outstanding_interest, Decimal("0.00"))
        post_repayment(loan=self.loan, amount=Decimal("8000.00"), user=self.officer)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, LoanAccount.CLOSED)
        self.assertEqual(self.loan.outstanding_principal, Decimal("0.00"))
        self.assertIsNotNone(self.loan.closed_at)
        self.assertTrue(LoanTransaction.objects.filter(loan=self.loan, transaction_type=LoanTransaction.REPAYMENT).count() >= 1)

    def test_repayment_exceeding_outstanding_is_rejected(self):
        with self.assertRaises(ValueError):
            post_repayment(loan=self.loan, amount=Decimal("30000.00"), user=self.officer)

    def test_penalty_is_settled_before_installments(self):
        penalty = LoanPenalty.objects.create(
            loan=self.loan, installment=None, amount=Decimal("600.00"),
            reason="Debit order charge", status=LoanPenalty.Status.OPEN,
            created_by=self.officer,
        )
        self.loan.outstanding_penalty = Decimal("600.00")
        self.loan.save(update_fields=["outstanding_penalty"])
        loan_tx, allocation = post_repayment(loan=self.loan, amount=Decimal("10000.00"), user=self.officer)
        self.assertEqual(allocation["penalty_paid"], Decimal("600.00"))
        self.assertEqual(allocation["interest_paid"], Decimal("2000.00"))
        self.assertEqual(allocation["principal_paid"], Decimal("7400.00"))
        penalty.refresh_from_db()
        self.assertEqual(penalty.status, LoanPenalty.Status.PAID)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.outstanding_penalty, Decimal("0.00"))

    def test_manual_self_service_repayment_keeps_savings_leg(self):
        result = post_installment_repayment(
            loan=self.loan, installment_number=1, account=self.account, user=self.officer,
        )
        self.assertTrue(result.is_paid)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("90000.00"))
        self.assertEqual(
            FinancialTransaction.objects.filter(
                idempotency_key=f"rep-{LoanTransaction.objects.filter(loan=self.loan).latest('id').reference}"
            ).count(),
            1,
        )

    def test_self_service_partial_repayment_posts_requested_amount(self):
        result = post_installment_repayment(
            loan=self.loan, installment_number=1, account=self.account, user=self.officer,
            amount=Decimal("5000.00"),
        )
        self.assertFalse(result.is_paid)
        self.assertEqual(result.partially_paid_amount, Decimal("5000.00"))
        self.assertEqual(result.status, LoanSchedule.Status.PARTIALLY_PAID)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("95000.00"))


class BalanceAndCancelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.loan_officer = _make_user("p3flow@example.com", "p3flow", User.LOAN)
        self.manager = _make_user("p3mgr@example.com", "p3mgr", User.MANAGER)
        self.member = _make_member(number="5001")
        self.savings = SavingsProduct.objects.create(
            name="P3 Savings", code="P3S", minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"), withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )
        self.account = SavingsAccount.objects.create(member=self.member, product=self.savings, balance=Decimal("100000.00"))
        self.product = _make_product()

    def _application(self):
        app = LoanApplication.objects.create(
            member=self.member,
            loan_type=self.product,
            requested_amount=Decimal("120000.00"),
            purpose="Flow test",
            repayment_period_months=12,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            created_by=self.loan_officer,
            status=LoanApplication.Status.UNDER_REVIEW,
        )
        return app

    def test_member_cancel_workflow(self):
        app = self._application()
        self.client.force_authenticate(self.manager)
        cancel = self.client.post(f"/api/v1/loans/{app.application_number}/cancel/", {"reason": "Changed mind"}, format="json")
        self.assertEqual(cancel.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, LoanApplication.Status.CANCELLED)
        self.assertIsNotNone(app.cancelled_by)
        self.assertTrue(
            AuditEvent.objects.filter(action="loan.application.cancelled", reference=app.application_number).exists()
        )
        reapprove = self.client.post(f"/api/v1/loans/{app.application_number}/approve/", {}, format="json")
        self.assertEqual(reapprove.status_code, 400)

    def test_balance_endpoint_is_authoritative_and_includes_penalty(self):
        app = self._application()
        approve_application(application=app, user=self.manager)
        loan = disburse_application(application=app, account=self.account, user=self.loan_officer)
        loan.outstanding_penalty = Decimal("1500.00")
        loan.save(update_fields=["outstanding_penalty"])
        expected_interest = sum(Decimal(row.interest_due) for row in loan.schedule.all())
        self.assertEqual(loan.total_outstanding, Decimal(loan.outstanding_principal) + Decimal(loan.outstanding_interest) + Decimal("1500.00"))
        self.assertEqual(loan.outstanding_interest, expected_interest)

    def test_disburse_posts_single_keyed_companion_journal(self):
        app = self._application()
        approve_application(application=app, user=self.manager)
        disburse_application(application=app, account=self.account, user=self.loan_officer)
        self.assertEqual(
            FinancialTransaction.objects.filter(idempotency_key=f"disb-{app.application_number}").count(),
            1,
        )
        loan = LoanAccount.objects.get(application=app)
        self.assertTrue(
            LoanTransaction.objects.filter(loan=loan, reference=f"LTX-{app.application_number}").exists()
        )
        self.assertEqual(loan.interest_type, self.product.interest_type)