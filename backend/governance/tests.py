"""Phase 4 governance & approval engine tests (spec).

Covers: automated withdrawals (auto-approve & dispatch, review routing),
fund reservation & concurrency safety, policy thresholds (min/max/auto/frequency),
segregation of duties, duplicate-approval blocking, cross-group visibility,
two-level committee review, expiry, cancellation, the officer inbox/action APIs,
group withdrawal-policy configuration, and the loans observation adapter.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import SavingsAccount, SavingsProduct
from groups.models import GroupMembership, VikobaGroup
from loans.models import LoanApplication, LoanProduct
from members.models import Member
from users.models import User

from governance import workflow
from governance.errors import ApprovalError
from governance.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    Decision,
    GroupWithdrawalPolicy,
    RequestType,
    RequiredLevel,
)
from governance.withdrawals import (
    ACTIVE_RESERVATION_STATUSES,
    available_balance,
    request_for,
    submit_withdrawal,
)

MIN_PAYOUT = 5000


def _make_user(email, username, role):
    return User.objects.create_user(
        email=email,
        username=username,
        password="test-password-123",
        role=role,
    )


def _make_member(user, phone="+255700000001", verified=True):
    return Member.objects.create(
        user=user,
        first_name="Phase",
        last_name="Four",
        phone_number=phone,
        email=user.email,
        date_of_birth="1990-01-01",
        country="Tanzania",
        is_verified=verified,
        phone_verified=verified,
    )


def _make_savings(member, balance="50000.00"):
    from uuid import uuid4

    suffix = uuid4().hex[:6].upper()
    product = SavingsProduct.objects.create(
        name=f"Gov Savings {suffix}",
        code=f"GOV{suffix}",
        minimum_balance=Decimal("0.00"),
        interest_rate=Decimal("2.50"),
        withdrawal_fee=Decimal("0.00"),
        allows_withdrawals=True,
    )
    return SavingsAccount.objects.create(member=member, product=product, balance=Decimal(balance))


def _make_group(name="Gov Group"):
    return VikobaGroup.objects.create(name=name)


def _membership(member, group, role):
    return GroupMembership.objects.create(member=member, group=group, role=role, is_active=True)


def _policy(group, **overrides):
    defaults = {
        "auto_approve_limit": Decimal("50000.00"),
        "max_withdrawal_limit": Decimal("50000.00"),
        "min_withdrawal_amount": None,
        "weekly_withdrawal_limit": None,
        "weekly_withdrawal_count": None,
        "monthly_withdrawal_limit": None,
        "min_retained_ratio": Decimal("0"),
        "review_levels": GroupWithdrawalPolicy.REVIEW_SINGLE,
        "reviewer_role": GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT,
    }
    defaults.update(overrides)
    policy, _ = GroupWithdrawalPolicy.objects.get_or_create(group=group, defaults=defaults)
    for key, value in defaults.items():
        setattr(policy, key, value)
    policy.save()
    return policy


class WithdrawalEngineTests(TestCase):
    """Straight-through processing, review routing, reservation & SoD."""

    def setUp(self):
        self.member_user = _make_user("member@example.com", "member", User.MEMBER)
        self.member = _make_member(self.member_user)
        self.treasurer_user = _make_user("treasurer@example.com", "treasurer", User.MEMBER)
        self.treasurer = _make_member(self.treasurer_user, phone="+255700000002")
        self.chair_user = _make_user("chair@example.com", "chair", User.MEMBER)
        self.chair = _make_member(self.chair_user, phone="+255700000003")
        self.group = _make_group()
        _membership(self.member, self.group, "MEMBER")
        _membership(self.treasurer, self.group, "TREASURER")
        _membership(self.chair, self.group, "CHAIRPERSON")
        self.policy = _policy(self.group)
        self.account = _make_savings(self.member)

    def _submit(self, amount, **kwargs):
        return submit_withdrawal(
            member=self.member,
            account=self.account,
            amount=amount,
            narration="test withdrawal",
            network="mpesa",
            requester=self.member_user,
            group=self.group,
            **kwargs,
        )

    def test_auto_approve_below_snippe_minimum_completes_officer_handled(self):
        result = self._submit("800.00")
        self.assertTrue(result.is_auto)
        self.assertFalse(result.review_required)
        self.assertIsNone(result.payout)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "APPROVED")
        approval = request_for(result.withdrawal)
        self.assertEqual(approval.status, ApprovalStatus.COMPLETED)
        self.assertEqual(approval.decision, Decision.AUTO_APPROVED)
        self.assertTrue(approval.actions.filter(action=ApprovalAction.ACTION_AUTO_APPROVE).exists())

    def test_auto_approve_above_minimum_dispatches_payout_without_debit(self):
        result = self._submit("20000.00")
        self.assertTrue(result.is_auto)
        self.assertIsNotNone(result.payout)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "SENT_TO_SNIPPE")
        approval = request_for(result.withdrawal)
        self.assertEqual(approval.status, ApprovalStatus.PROCESSING)
        # No ledger debit until payout.completed — funds still on the account.
        self.assertEqual(Decimal(str(self.account.balance)), Decimal("50000.00"))

    def test_above_auto_threshold_routes_to_manual_review(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00")
        self.assertTrue(result.is_review)
        self.assertTrue(result.review_required)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "PENDING")
        approval = result.approval
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertEqual(approval.required_role, GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT)
        self.assertTrue(approval.actions.filter(action=ApprovalAction.ACTION_REVIEW_REQUIRED).exists())

    def test_officer_approval_executes_dispatch(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00")
        request = result.approval
        approved = workflow.approve(request=request, user=self.treasurer_user, reason="OK")
        self.assertEqual(approved.status, ApprovalStatus.PROCESSING)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "SENT_TO_SNIPPE")
        self.assertTrue(
            result.withdrawal.payment_transactions.filter(transaction_type="WITHDRAWAL").exists()
        )
        self.assertTrue(
            approved.actions.filter(
                action=ApprovalAction.ACTION_APPROVE, actor_type=ApprovalAction.ACTOR_HUMAN
            ).exists()
        )

    def test_insufficient_available_balance_is_rejected(self):
        _policy(self.group, auto_approve_limit=None, max_withdrawal_limit=None)
        with self.assertRaises(ApprovalError) as ctx:
            self._submit("60000.00")
        self.assertEqual(ctx.exception.code, ApprovalError.INSUFFICIENT_AVAILABLE_BALANCE)
        active = ApprovalRequest.objects.filter(
            status__in=[ApprovalStatus.PENDING, ApprovalStatus.APPROVED]
        )
        self.assertFalse(active.exists())

    def test_reservation_blocks_double_spend(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        first = self._submit("30000.00")
        self.assertTrue(first.is_review)
        with self.assertRaises(ApprovalError) as ctx:
            self._submit("30000.00")
        self.assertEqual(ctx.exception.code, ApprovalError.INSUFFICIENT_AVAILABLE_BALANCE)
        # Available balance excludes the active reservation.
        self.assertEqual(available_balance(self.account), Decimal("20000.00"))

    def test_rejection_releases_reservation(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        first = self._submit("30000.00")
        workflow.reject(request=first.approval, user=self.treasurer_user, reason="Not needed")
        first.withdrawal.refresh_from_db()
        self.assertEqual(first.withdrawal.status, "REJECTED")
        self.assertEqual(available_balance(self.account), Decimal("50000.00"))
        later = self._submit("800.00")
        self.assertTrue(later.is_auto)

    def test_maximum_limit_is_hard_rejected(self):
        _policy(self.group, max_withdrawal_limit=Decimal("100000.00"))
        with self.assertRaises(ApprovalError) as ctx:
            self._submit("150000.00")
        self.assertEqual(ctx.exception.code, ApprovalError.WITHDRAWAL_LIMIT_EXCEEDED)

    def test_segregation_of_duties_blocks_self_approval(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00")
        with self.assertRaises(ApprovalError) as ctx:
            workflow.approve(request=result.approval, user=self.member_user)
        self.assertEqual(ctx.exception.code, ApprovalError.SELF_APPROVAL_NOT_ALLOWED)

    def test_unauthorized_member_cannot_approve(self):
        outsider_user = _make_user("outsider@example.com", "outsider", User.MEMBER)
        _make_member(outsider_user, phone="+255700000004")
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00")
        with self.assertRaises(ApprovalError) as ctx:
            workflow.approve(request=result.approval, user=outsider_user)
        self.assertEqual(ctx.exception.code, ApprovalError.UNAUTHORIZED_APPROVAL)

    def test_duplicate_approval_is_blocked(self):
        _policy(
            self.group,
            auto_approve_limit=Decimal("10000.00"),
            review_levels=GroupWithdrawalPolicy.REVIEW_TWO_LEVEL,
        )
        result = self._submit("20000.00")
        workflow.approve(request=result.approval, user=self.treasurer_user)
        with self.assertRaises(ApprovalError) as ctx:
            workflow.approve(request=result.approval, user=self.treasurer_user)
        self.assertEqual(ctx.exception.code, ApprovalError.DUPLICATE_APPROVAL)

    def test_two_level_review_needs_treasurer_then_chairperson(self):
        _policy(
            self.group,
            auto_approve_limit=Decimal("10000.00"),
            review_levels=GroupWithdrawalPolicy.REVIEW_TWO_LEVEL,
            reviewer_role=GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT,
        )
        result = self._submit("20000.00")
        approval = result.approval
        self.assertEqual(list(approval.steps.values_list("role", flat=True)), ["TREASURER", "CHAIRPERSON"])

        after_treasurer = workflow.approve(request=approval, user=self.treasurer_user)
        self.assertEqual(after_treasurer.status, ApprovalStatus.PENDING)
        self.assertEqual(after_treasurer.steps.get(role="TREASURER").status, ApprovalStep.Status.APPROVED)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "PENDING")

        # Chairperson approves the second level — request executes.
        after_chair = workflow.approve(request=approval, user=self.chair_user)
        self.assertEqual(after_chair.status, ApprovalStatus.PROCESSING)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "SENT_TO_SNIPPE")

    def test_expired_request_cannot_be_approved(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00", expires_hours=-24)
        with self.assertRaises(ApprovalError) as ctx:
            workflow.approve(request=result.approval, user=self.treasurer_user)
        self.assertEqual(ctx.exception.code, ApprovalError.REQUEST_EXPIRED)
        result.approval.refresh_from_db()
        self.assertEqual(result.approval.status, ApprovalStatus.EXPIRED)
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "CANCELLED")

    def test_requester_can_cancel_and_reservation_releases(self):
        _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        result = self._submit("20000.00")
        workflow.cancel(request=result.approval, user=self.member_user, reason="Changed my mind")
        result.withdrawal.refresh_from_db()
        self.assertEqual(result.withdrawal.status, "CANCELLED")
        self.assertEqual(available_balance(self.account), Decimal("50000.00"))

    def test_frequency_rule_routes_to_manual_review(self):
        _policy(self.group, weekly_withdrawal_count=1)
        self._submit("800.00")  # auto, counts toward weekly frequency
        result = self._submit("800.00")
        self.assertTrue(result.is_review)

    def test_platform_defaults_apply_without_group(self):
        solo_user = _make_user("solo@example.com", "solo", User.MEMBER)
        solo = _make_member(solo_user, phone="+255700000005")
        account = _make_savings(solo)
        result = submit_withdrawal(
            member=solo,
            account=account,
            amount="7000.00",
            requester=solo_user,
            network="mpesa",
        )
        self.assertTrue(result.is_auto)
        self.assertIsNotNone(result.payout)


class GovernanceApiTests(TestCase):
    """Inbox / detail / action / history / policy-config endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.member_user = _make_user("member@example.com", "member", User.MEMBER)
        self.member = _make_member(self.member_user)
        self.treasurer_user = _make_user("treasurer@example.com", "treasurer", User.MEMBER)
        self.treasurer = _make_member(self.treasurer_user, phone="+255700000002")
        self.officer_user = _make_user("ops@example.com", "ops", User.OPERATION)
        self.group = _make_group()
        _membership(self.member, self.group, "MEMBER")
        _membership(self.treasurer, self.group, "TREASURER")
        other_group = _make_group("Other Group")
        other_user = _make_user("other@example.com", "other", User.MEMBER)
        other_member = _make_member(other_user, phone="+255700000006")
        _membership(other_member, other_group, "CHAIRPERSON")
        self.other_group = other_group
        self.other_member_user = other_user

        self.policy = _policy(self.group, auto_approve_limit=Decimal("10000.00"))
        self.account = _make_savings(self.member)
        self.result = submit_withdrawal(
            member=self.member,
            account=self.account,
            amount="20000.00",
            requester=self.member_user,
            group=self.group,
            policy=self.policy,
            network="mpesa",
        )
        self.approval = self.result.approval

    def _get(self, url, user):
        self.client.force_authenticate(user=user)
        return self.client.get(url)

    def _post(self, url, user, data=None):
        self.client.force_authenticate(user=user)
        return self.client.post(url, data or {}, format="json")

    def test_inbox_visible_to_group_committee_and_staff(self):
        treasurer = self._get("/api/v1/governance/approvals/", self.treasurer_user)
        self.assertEqual(treasurer.status_code, 200)
        self.assertEqual(len(treasurer.data), 1)
        staff = self._get("/api/v1/governance/approvals/", self.officer_user)
        self.assertEqual(staff.status_code, 200)
        self.assertEqual(len(staff.data), 1)

    def test_cross_group_isolation_on_reads(self):
        unseen = self._get("/api/v1/governance/approvals/", self.other_member_user)
        self.assertEqual(len(unseen.data), 0)
        missing = self._get(
            f"/api/v1/governance/approvals/{self.approval.pk}/", self.other_member_user
        )
        self.assertEqual(missing.status_code, 404)

    def test_action_endpoint_approve(self):
        resp = self._post(
            f"/api/v1/governance/approvals/{self.approval.pk}/action/",
            self.treasurer_user,
            {"action": "approve", "reason": "Examined finances"},
        )
        self.assertEqual(resp.status_code, 200)
        self.approval.refresh_from_db()
        self.result.withdrawal.refresh_from_db()
        self.assertEqual(self.result.withdrawal.status, "SENT_TO_SNIPPE")

    def test_action_endpoint_unauthorized(self):
        resp = self._post(
            f"/api/v1/governance/approvals/{self.approval.pk}/action/",
            self.member_user,
            {"action": "approve"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get("code"), ApprovalError.SELF_APPROVAL_NOT_ALLOWED)

    def test_history_is_append_only_audit(self):
        self._post(
            f"/api/v1/governance/approvals/{self.approval.pk}/action/",
            self.treasurer_user,
            {"action": "approve"},
        )
        actions = self._get(
            f"/api/v1/governance/approvals/{self.approval.pk}/history/", self.treasurer_user
        )
        self.assertEqual(actions.status_code, 200)
        kinds = [a["actor_type"] for a in actions.data]
        self.assertIn(ApprovalAction.ACTOR_SYSTEM, kinds)
        self.assertIn(ApprovalAction.ACTOR_HUMAN, kinds)

    def test_policy_read_by_committee_and_staff(self):
        resp = self._get(f"/api/v1/governance/groups/{self.group.pk}/withdrawal-policy/", self.treasurer_user)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["auto_approve_limit"], Decimal("10000.00"))
        staff = self._get(f"/api/v1/governance/groups/{self.group.pk}/withdrawal-policy/", self.officer_user)
        self.assertEqual(staff.status_code, 200)

    def test_policy_update_audited_and_effective(self):
        self.client.force_authenticate(user=self.treasurer_user)
        resp = self.client.put(
            f"/api/v1/governance/groups/{self.group.pk}/withdrawal-policy/",
            {"auto_approve_limit": "25000.00", "review_levels": GroupWithdrawalPolicy.REVIEW_TWO_LEVEL},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.group.withdrawal_policy.refresh_from_db()
        self.assertEqual(self.group.withdrawal_policy.auto_approve_limit, Decimal("25000.00"))
        # A policy change leaves a HUMAN audit row keyed without a request.
        self.assertTrue(
            ApprovalAction.objects.filter(
                actor_type=ApprovalAction.ACTOR_HUMAN, action="policy_changed", request=None
            ).exists()
        )

    def test_plain_member_cannot_read_policy(self):
        resp = self._get(f"/api/v1/governance/groups/{self.group.pk}/withdrawal-policy/", self.member_user)
        self.assertEqual(resp.status_code, 403)

    def test_remote_read_of_own_request_via_inbox_bool_flags(self):
        detail = self._get(f"/api/v1/governance/approvals/{self.approval.pk}/", self.member_user)
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.data["is_requester"])
        self.assertFalse(detail.data["can_act"])


class LoanGovernanceAdapterTests(TestCase):
    """Loan decisions are observed by the governance engine."""

    def setUp(self):
        self.officer = _make_user("lo@example.com", "lo", User.LOAN)
        self.member_user = _make_user("loanmember@example.com", "loanmember", User.MEMBER)
        self.member = _make_member(self.member_user, phone="+255700000007")
        self.group = _make_group()
        self.loan_product = LoanProduct.objects.create(
            name="Gov Loan",
            interest_rate=Decimal("12.00"),
            repayment_period_months=12,
            multiplier=Decimal("3.00"),
            min_amount=Decimal("1000.00"),
            max_amount=Decimal("500000.00"),
            max_term_months=24,
            interest_type=LoanProduct.FLAT,
            is_active=True,
        )
        SavingsProduct.objects.create(
            name="Loan Savings",
            code="LOAN",
            minimum_balance=Decimal("0.00"),
            interest_rate=Decimal("2.50"),
            withdrawal_fee=Decimal("0.00"),
            allows_withdrawals=True,
        )

    def _application(self, status=LoanApplication.Status.UNDER_REVIEW):
        return LoanApplication.objects.create(
            member=self.member,
            loan_type=self.loan_product,
            group=self.group,
            requested_amount=Decimal("120000.00"),
            purpose="Governance test",
            repayment_period_months=12,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            created_by=self.officer,
            status=status,
        )

    def test_loan_approval_is_recorded(self):
        from governance.loans import record_loan_decision

        app = self._application()
        record_loan_decision(application=app, user=self.officer, action="approved", reason="Qualified")
        request = ApprovalRequest.objects.get(request_type=RequestType.LOAN_APPLICATION, object_id=app.pk)
        self.assertEqual(request.status, ApprovalStatus.APPROVED)
        self.assertTrue(
            request.actions.filter(action=ApprovalAction.ACTION_APPROVE, actor_type=ApprovalAction.ACTOR_HUMAN).exists()
        )

    def test_loan_cancellation_is_recorded(self):
        from governance.loans import record_loan_decision

        app = self._application(status=LoanApplication.Status.SUBMITTED)
        record_loan_decision(application=app, user=self.officer, action="cancelled", reason="Withdrew")
        request = ApprovalRequest.objects.get(request_type=RequestType.LOAN_APPLICATION, object_id=app.pk)
        self.assertEqual(request.status, ApprovalStatus.CANCELLED)
        self.assertTrue(request.actions.filter(action=ApprovalAction.ACTION_CANCEL).exists())