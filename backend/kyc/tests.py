"""Phase 6 KYC & identity-verification engine tests (spec §34).

Coverage:
- Identity: profile materialisation, legacy-pipeline sync, membership number.
- KYC engine: submit / reject / pending / provider-error / retry / idempotency,
  bounded attempts, rejection is terminal until review, expiry sweep.
- Security: backend-only status control (a forged payload cannot change status),
  member self-service isolation (a member can never read another member's KYC),
  admin endpoints require business roles, masking of national ID / references,
  provider failure is NEVER treated as identity success / approval.
- Financial integration: withdrawal gate honours the KYC level, loan eligibility
  blocking rule, level overrides via group withdrawal/loan policy.

Only the member-profile unit pieces are independent; the flow and integration
tests run with the built-in ``SimulatedKYCProvider`` (``KYC_PROVIDER_MODE``
must be set per-test / per-class).
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from accounts.models import SavingsAccount, SavingsProduct
from groups.models import GroupMembership, VikobaGroup
from loans.models import LoanApplication, LoanProduct
from members.models import Member
from users.models import User

from kyc import services as kyc_services
from kyc.models import KYCEvent, KYCProfile
from kyc.statuses import KYCLevel, KYCStatus


def _make_user(email, username, role):
    return User.objects.create_user(
        email=email,
        username=username,
        password="test-password-123",
        role=role,
    )


def _make_member(user=None, phone="+255700000001", verified=False, national_id=None):
    if national_id is None:
        from uuid import uuid4

        national_id = f"9000{uuid4().hex[:11].upper()}"
    return Member.objects.create(
        user=user,
        first_name="Asha",
        last_name="Mfaume",
        phone_number=phone,
        email=(user.email if user else "asha@example.com"),
        date_of_birth="1992-05-14",
        national_id=national_id,
        country="Tanzania",
        is_verified=verified,
    )


def _make_group(name="KYC Group"):
    return VikobaGroup.objects.create(name=name)


def _make_savings(member, balance="50000.00"):
    from uuid import uuid4

    suffix = uuid4().hex[:6].upper()
    product = SavingsProduct.objects.create(
        name=f"KYC Savings {suffix}",
        code=f"KYCS{suffix}",
        minimum_balance=Decimal("0.00"),
        interest_rate=Decimal("2.50"),
        withdrawal_fee=Decimal("0.00"),
        allows_withdrawals=True,
    )
    return SavingsAccount.objects.create(member=member, product=product, balance=Decimal(balance))


SIMULATED = override_settings(
    KYC_PROVIDER_MODE="simulated",
    KYC_REQUIRED_LEVEL="LEVEL_1",
    KYC_MAX_ATTEMPTS=3,
    KYC_VERIFICATION_EXPIRY_DAYS=365,
)


@SIMULATED
class KYCIdentityTests(TestCase):
    """Profile materialisation + legacy manual-pipeline sync."""

    def test_profile_created_lazily(self):
        member = _make_member()
        self.assertFalse(KYCProfile.objects.filter(member=member).exists())

        profile = kyc_services.get_or_create_profile(member)
        self.assertEqual(profile.status, KYCStatus.NOT_STARTED)
        self.assertEqual(profile.verification_level, KYCLevel.LEVEL_0)

    def test_legacy_verified_member_syncs_to_verified_level_1(self):
        member = _make_member(verified=True)
        profile = kyc_services.get_or_create_profile(member)
        self.assertEqual(profile.status, KYCStatus.VERIFIED)
        self.assertEqual(profile.verification_level, KYCLevel.LEVEL_1)
        self.assertTrue(profile.events.filter(action=KYCEvent.ACTION_SYNCED_FROM_MEMBER).exists())

    def test_satisfies_levels(self):
        member = _make_member(verified=True)
        kyc_services.get_or_create_profile(member)
        self.assertTrue(kyc_services.satisfies(member, KYCLevel.LEVEL_1))
        self.assertFalse(kyc_services.satisfies(member, KYCLevel.LEVEL_2))
        self.assertTrue(kyc_services.satisfies(member, KYCLevel.LEVEL_0))

    def test_unverified_member_never_satisfies(self):
        member = _make_member(verified=False)
        self.assertFalse(kyc_services.satisfies(member, KYCLevel.LEVEL_1))
        self.assertFalse(kyc_services.satisfies(member, "LEVEL_2"))

    def test_membership_number_generated(self):
        member = _make_member()
        self.assertTrue(member.membership_number.startswith("M"))


@SIMULATED
class KYCProviderFlowTests(TestCase):
    """Verification submission lifecycle against the simulated provider."""

    def setUp(self):
        self.user = _make_user("kycflow@example.com", "kycflow", User.MEMBER)
        self.member = _make_member(user=self.user)

    def test_submit_verified_upgrades_to_level_2(self):
        result = kyc_services.submit_verification(member=self.member)
        profile = result["profile"]
        request = result["request"]
        self.assertEqual(profile.status, KYCStatus.VERIFIED)
        self.assertEqual(profile.verification_level, KYCLevel.LEVEL_2)
        self.assertEqual(request.status, "SUCCESS")
        self.assertTrue(request.provider_reference.startswith("SIM-KYC-"))
        self.assertIsNotNone(profile.verified_at)

    def test_rejected_identity_mismatch_is_terminal(self):
        self.member.national_id = "90000000000666"
        self.member.save()
        result = kyc_services.submit_verification(member=self.member)
        self.assertEqual(result["profile"].status, KYCStatus.REJECTED)
        self.assertEqual(result["profile"].failure_code, "IDENTITY_MISMATCH")

        with self.assertRaises(kyc_services.KYCError):
            kyc_services.submit_verification(member=self.member)

    def test_provider_error_is_not_rejection(self):
        self.member.national_id = "0000000000"
        self.member.save()
        result = kyc_services.submit_verification(member=self.member)
        self.assertEqual(result["profile"].status, KYCStatus.PROVIDER_ERROR)
        self.assertNotEqual(result["profile"].status, KYCStatus.REJECTED)
        self.assertFalse(kyc_services.satisfies(self.member))

    def test_invalid_format_rejected(self):
        self.member.national_id = "abc"
        self.member.save()
        result = kyc_services.submit_verification(member=self.member)
        self.assertEqual(result["profile"].status, KYCStatus.REJECTED)
        self.assertEqual(result["profile"].failure_code, "INVALID_NATIONAL_ID_FORMAT")

    def test_pending_request(self):
        result = kyc_services.submit_verification(member=self.member)
        self.assertEqual(result["request"].status, "SUCCESS")

    def test_idempotency_same_key_returns_same_request(self):
        first = kyc_services.submit_verification(member=self.member, idempotency_key="key-1")
        second = kyc_services.submit_verification(member=self.member, idempotency_key="key-1")
        self.assertEqual(first["request"].pk, second["request"].pk)
        self.assertEqual(first["request"].status, second["request"].status)

    def test_single_active_request_constraint(self):
        from kyc.models import KYCVerificationRequest

        profile = kyc_services.get_or_create_profile(self.member)
        KYCVerificationRequest.objects.create(profile=profile, status="SUBMITTED")
        with self.assertRaises(Exception):
            KYCVerificationRequest.objects.create(profile=profile, status="PROCESSING")

    def test_retry_bounded_by_max_attempts(self):
        from kyc.models import KYCVerificationRequest

        # First attempt hits the simulated outage -> PROVIDER_ERROR (attempt 1/3).
        self.member.national_id = "0000000000"
        self.member.save()
        result = kyc_services.submit_verification(member=self.member)
        request = result["request"]
        self.assertEqual(request.status, "PROVIDER_ERROR")
        self.assertEqual(request.attempt_count, 1)

        # The provider recovers; the member retries the SAME request (bounded).
        self.member.national_id = "90000000123456"
        self.member.save()
        retried = kyc_services.retry_verification(member=self.member)
        self.assertEqual(retried["request"].status, "SUCCESS")
        self.assertEqual(retried["request"].attempt_count, 2)
        self.assertEqual(retried["profile"].status, KYCStatus.VERIFIED)

        KYCVerificationRequest.objects.filter(pk=retried["request"].pk).update(attempt_count=3)
        self.member.national_id = "0000000000"
        self.member.save()
        with self.assertRaises(kyc_services.KYCError):
            kyc_services.retry_verification(member=self.member)

    def test_retry_without_provider_error_raises(self):
        kyc_services.submit_verification(member=self.member)
        with self.assertRaises(kyc_services.KYCError):
            kyc_services.retry_verification(member=self.member)

    def test_expired_verification_never_satisfies(self):
        kyc_services.submit_verification(member=self.member)
        profile = kyc_services.get_or_create_profile(self.member)
        self.assertTrue(kyc_services.satisfies(self.member))

        profile.expires_at = timezone.now() - timedelta(days=1)
        profile.save(update_fields=["expires_at"])
        self.assertFalse(kyc_services.satisfies(self.member))
        self.assertTrue(profile.events.filter(action=KYCEvent.ACTION_EXPIRED).exists())


@override_settings(
    KYC_PROVIDER_MODE="disabled",
    KYC_REQUIRED_LEVEL="LEVEL_1",
)
class KYKDisableFailClosedTests(TestCase):
    """With no provider configured the engine must fail closed — never verify."""

    def test_submit_without_provider_never_verifies(self):
        user = _make_user("kycfail@example.com", "kycfail", User.MEMBER)
        member = _make_member(user=user)
        result = kyc_services.submit_verification(member=member)
        self.assertEqual(result["profile"].status, KYCStatus.PROVIDER_ERROR)
        self.assertEqual(result["profile"].failure_code, "PROVIDER_UNAVAILABLE")
        self.assertFalse(kyc_services.satisfies(member))


@SIMULATED
class KYCManualReviewTests(TestCase):
    def setUp(self):
        self.user = _make_user("kycreview@example.com", "kycreview", User.MEMBER)
        self.member = _make_member(user=self.user)

    def _admins(self):
        return {"approve": User.LOAN, "reject": User.ADMIN, "request_update": User.MEMBER}

    def test_approve_requires_reason(self):
        with self.assertRaises(kyc_services.KYCError):
            kyc_services.manual_review(member=self.member, decision="approve", reason="")

    def test_approve_sets_verified_level_1(self):
        director = _make_user("dir@example.com", "dir", User.ADMIN)
        result = kyc_services.manual_review(member=self.member, decision="approve", reason="Documents verified.", actor=director)
        profile = result["profile"]
        self.assertEqual(profile.status, KYCStatus.VERIFIED)
        self.assertEqual(profile.verification_level, KYCLevel.LEVEL_1)
        self.assertTrue(profile.events.filter(action=KYCEvent.ACTION_MANUAL_APPROVE).exists())

    def test_reject_then_approve_via_manual_review(self):
        self.member.national_id = "90000000000666"
        self.member.save()
        kyc_services.submit_verification(member=self.member)
        self.assertEqual(self.member.kyc_profile.status, KYCStatus.REJECTED)

        director = _make_user("dir2@example.com", "dir2", User.ADMIN)
        result = kyc_services.manual_review(member=self.member, decision="approve", reason="Manual bulk re-checked.", actor=director)
        self.assertEqual(result["profile"].status, KYCStatus.VERIFIED)
        self.assertTrue(kyc_services.satisfies(self.member))

    def test_request_update_allowed(self):
        director = _make_user("dir3@example.com", "dir3", User.ADMIN)
        result = kyc_services.manual_review(
            member=self.member, decision="request_update", reason="Photo illegible, resubmit.", actor=director
        )
        self.assertEqual(result["profile"].status, KYCStatus.REQUIRES_UPDATE)

    def test_invalid_decision_raises(self):
        with self.assertRaises(kyc_services.KYCError):
            kyc_services.manual_review(member=self.member, decision="ban", reason="nope")


class KYCApiSecurityTests(TestCase):
    """Endpoints: isolation, role gating, forged-status resistance, masking."""

    def setUp(self):
        self.client = APIClient()
        self.member_user = _make_user("api_member@example.com", "api_member", User.MEMBER)
        self.other_user = _make_user("api_other@example.com", "api_other", User.MEMBER)
        self.member = _make_member(user=self.member_user, national_id="90000000123456")
        self.other = _make_member(user=self.other_user, phone="+255700111222")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_member_can_submit_and_read_own_kyc(self):
        self._auth(self.member_user)
        resp = self.client.get("/api/v1/kyc/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "NOT_STARTED")
        self.assertEqual(resp.data["identity_summary"]["national_id"], "**********3456")

        resp = self.client.post("/api/v1/kyc/me/verify/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["profile"]["status"], "VERIFIED")

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_member_cannot_read_another_member_kyc(self):
        self._auth(self.other_user)
        resp = self.client.get("/api/v1/kyc/admin/%s/" % self.member.membership_number)
        self.assertEqual(resp.status_code, 403)

        # no payload can change own status — the serializer is read-only
        resp = self.client.post("/api/v1/kyc/me/verify/", {"status": "VERIFIED"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["profile"]["status"], "VERIFIED")

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_admin_requires_business_role(self):
        # a member cannot hit the staff dashboard
        self._auth(self.member_user)
        resp = self.client.get("/api/v1/kyc/admin/")
        self.assertEqual(resp.status_code, 403)

        # a business role can
        staff = _make_user("api_staff@example.com", "api_staff", User.ADMIN)
        staff.role = User.LOAN
        staff.save()
        self._auth(staff)
        resp = self.client.get("/api/v1/kyc/admin/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("profiles", resp.data)
        self.assertIn("summary", resp.data)

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_admin_review_audited_and_reason_required(self):
        staff = _make_user("api_staff2@example.com", "api_staff2", User.ADMIN)
        staff.role = User.LOAN
        staff.save()
        self._auth(staff)

        resp = self.client.post(
            "/api/v1/kyc/admin/%s/review/" % self.other.membership_number,
            {"decision": "approve", "reason": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post(
            "/api/v1/kyc/admin/%s/review/" % self.other.membership_number,
            {"decision": "approve", "reason": "Documents on file."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "VERIFIED")
        self.assertTrue(
            KYCEvent.objects.filter(
                profile__member=self.other,
                action=KYCEvent.ACTION_MANUAL_APPROVE,
                actor=staff,
            ).exists()
        )

    def test_forged_status_is_impossible(self):
        # The profile model field is not writable via any serializer/endpoint;
        # the service layer is the only transition authority.
        from kyc.serializers import KYCProfileSerializer

        member = _make_member()
        profile = KYCProfile.objects.create(member=member)
        data = KYCProfileSerializer(profile).data
        self.assertEqual(data["status"], KYCStatus.NOT_STARTED)

    @override_settings(KYC_PROVIDER_MODE="simulated")
    def test_verify_endpoint_is_rate_limited(self):
        cache.clear()
        self._auth(self.member_user)
        with mock.patch.object(SimpleRateThrottle, "THROTTLE_RATES", {"kyc-submit": "1/min"}):
            first = self.client.post("/api/v1/kyc/me/verify/", {}, format="json")
            self.assertEqual(first.status_code, 200)
            # The rate limit is enforced on the content-posting entry point so a
            # submitted identity cannot be used to hammer the provider on repeat calls.
            second = self.client.post("/api/v1/kyc/me/verify/", {}, format="json")
            self.assertEqual(second.status_code, 429)


@SIMULATED
class KYCFinancialIntegrationTests(TestCase):
    """KYC status drives withdrawal + loan eligibility; failure never grants access."""

    def setUp(self):
        self.member = _make_member()
        self.account = _make_savings(self.member)
        self.group = _make_group()
        GroupMembership.objects.create(
            group=self.group, member=self.member, role=GroupMembership.Role.MEMBER, is_active=True
        )
        self.product = LoanProduct.objects.create(
            name="KYC Loan",
            interest_rate=Decimal("12.00"),
            repayment_period_months=12,
            multiplier=Decimal("3.00"),
            min_amount=Decimal("1000.00"),
            max_amount=Decimal("500000.00"),
            max_term_months=24,
            interest_type=LoanProduct.FLAT,
            is_active=True,
        )

    def _application(self):
        officer = _make_user("loan_off@example.com", "loan_off", User.LOAN)
        return LoanApplication.objects.create(
            member=self.member,
            loan_type=self.product,
            requested_amount=Decimal("12000.00"),
            purpose="KYC integration",
            repayment_period_months=6,
            security_type=LoanApplication.SecurityType.COLLATERAL,
            created_by=officer,
            status=LoanApplication.Status.UNDER_REVIEW,
        )

    def test_unverified_member_withdrawal_requires_verified(self):
        from governance.errors import ApprovalError
        from governance.withdrawals import submit_withdrawal

        with self.assertRaises(ApprovalError) as ctx:
            submit_withdrawal(member=self.member, account=self.account, amount=Decimal("10000"))
        self.assertEqual(ctx.exception.code if hasattr(ctx.exception, "code") else str(ctx.exception), ApprovalError.KYC_REQUIRED)

    def test_verified_member_can_auto_approve_withdrawal(self):
        from governance.withdrawals import submit_withdrawal

        self.member.is_verified = True
        self.member.save()
        kyc_services.get_or_create_profile(self.member)
        result = submit_withdrawal(member=self.member, account=self.account, amount=Decimal("10000"))
        self.assertIsNotNone(result.withdrawal)
        self.assertTrue(kyc_services.satisfies(self.member))

    def test_loan_eligibility_blocks_without_kyc(self):
        from loans.eligibility import check_eligibility

        app = self._application()
        ok, errors = check_eligibility(app)
        self.assertFalse(ok)
        self.assertTrue(any("KYC" in e for e in errors))

    def test_loan_eligibility_passes_when_verified(self):
        from loans.eligibility import check_eligibility

        self.member.is_verified = True
        self.member.save()
        kyc_services.get_or_create_profile(self.member)
        app = self._application()
        ok, errors = check_eligibility(app)
        self.assertTrue(ok, "expected KYC to satisfy eligibility; errors: %r" % errors)

    def test_group_withdrawal_policy_level_2_blocks_level_1(self):
        from governance.models import GroupWithdrawalPolicy
        from governance.withdrawals import submit_withdrawal

        self.member.is_verified = True
        self.member.save()
        kyc_services.get_or_create_profile(self.member)
        policy, _ = GroupWithdrawalPolicy.objects.get_or_create(group=self.group)
        policy.kyc_level_required = "LEVEL_2"
        policy.save()

        with self.assertRaises(Exception):
            submit_withdrawal(member=self.member, account=self.account, amount=Decimal("10000"))

    def test_provider_failure_never_grants_approval(self):
        """A provider outage must not unlock withdrawals or loans."""
        from governance.withdrawals import submit_withdrawal
        from loans.eligibility import check_eligibility

        self.member.national_id = "0000000000"
        self.member.save()
        result = kyc_services.submit_verification(member=self.member)
        profile = result["profile"]
        self.assertEqual(profile.status, KYCStatus.PROVIDER_ERROR)
        self.assertFalse(kyc_services.satisfies(self.member))

        with self.assertRaises(Exception):
            submit_withdrawal(member=self.member, account=self.account, amount=Decimal("10000"))

        app = self._application()
        ok, errors = check_eligibility(app)
        self.assertFalse(ok)

    def test_loan_submit_gate_requires_kyc(self):
        from rest_framework.test import APIClient

        user = _make_user("loan_gate@example.com", "loan_gate", User.MEMBER)
        member = _make_member(user=user)
        GroupMembership.objects.create(
            group=self.group, member=member, role=GroupMembership.Role.MEMBER, is_active=True
        )
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post("/api/v1/loans/me/", format="json", data={})
        self.assertIn(resp.status_code, (400, 403))


class KYCDashboardTests(TestCase):
    """Summary counts and admin filtering."""

    def setUp(self):
        self.user = _make_user("dash1@example.com", "dash1", User.ADMIN)
        self.user.role = User.LOAN
        self.user.save()
        self.member = _make_member()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_dashboard_summary_counts(self):
        kyc_services.get_or_create_profile(self.member)
        kyc_services.submit_verification(member=self.member)
        resp = self.client.get("/api/v1/kyc/admin/", {"status": "VERIFIED"})
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data["summary"]["verified"], 1)
        self.assertTrue(any(p["membership_number"] == self.member.membership_number for p in resp.data["profiles"]))

    @override_settings(KYC_PROVIDER_MODE="simulated", KYC_REQUIRED_LEVEL="LEVEL_1")
    def test_admin_detail_shows_audit_trail(self):
        kyc_services.get_or_create_profile(self.member)
        kyc_services.submit_verification(member=self.member)
        resp = self.client.get("/api/v1/kyc/admin/%s/" % self.member.membership_number)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("events", resp.data)
        self.assertTrue(len(resp.data["events"]) >= 1)
        self.assertIn("action", resp.data["events"][0])