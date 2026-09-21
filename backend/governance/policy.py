"""Deterministic withdrawal eligibility + decision policy.

Decisions are explainable: each evaluation returns the rules that passed and
the first rule that failed, plus the policy version that was in force.  Group
policy rows override platform defaults; ``None`` inherits.

Precedence:

1. Any hard rejection (minimum, maximum, retained balance, insufficient
   available balance) => ``REJECTED``.
2. Any manual-review condition (auto threshold exceeded, frequency, review
   flags) => ``MANUAL_REVIEW``.
3. Otherwise => ``AUTO_APPROVED``.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from governance.errors import ApprovalError
from governance.models import Decision, GroupWithdrawalPolicy

def _setting_decimal(name):
    value = getattr(settings, name, None)
    if value in (None, "", "None"):
        return None
    return Decimal(str(value))


# Platform defaults (groups inherit these; keep in sync with settings).
DEFAULT_AUTO_APPROVE_LIMIT = _setting_decimal("WITHDRAWAL_AUTO_LIMIT_TZS")
DEFAULT_MAX_WITHDRAWAL_LIMIT = _setting_decimal("WITHDRAWAL_MAX_LIMIT_TZS")
DEFAULT_MIN_WITHDRAWAL_AMOUNT = _setting_decimal("WITHDRAWAL_MIN_AMOUNT_TZS")
DEFAULT_MIN_RETAINED_RATIO = _setting_decimal("WITHDRAWAL_MIN_RETAINED_RATIO") or Decimal("0")
DEFAULT_POLICY_VERSION = getattr(settings, "WITHDRAWAL_POLICY_VERSION", "platform-default-v1")


@dataclass
class PolicyDecision:
    """The explainable outcome of :func:`evaluate_withdrawal`."""

    decision: str
    reason: str
    code: str = ""              # stable machine-readable failure/review code
    rules_passed: list = field(default_factory=list)
    failed_rules: list = field(default_factory=list)  # [{"code", "message"}]
    policy_version: str = DEFAULT_POLICY_VERSION
    required_level: str = Decision.MANUAL_REVIEW
    required_role: str = GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT
    review_levels: str = GroupWithdrawalPolicy.REVIEW_SINGLE
    metadata: dict = field(default_factory=dict)

    @property
    def is_auto(self):
        return self.decision == Decision.AUTO_APPROVED

    @property
    def is_review(self):
        return self.decision == Decision.MANUAL_REVIEW

    @property
    def is_rejected(self):
        return self.decision == Decision.REJECTED


def get_or_create_policy(group) -> GroupWithdrawalPolicy:
    """Lazy per-group withdrawal policy (mirrors loans.policies)."""
    policy, _ = GroupWithdrawalPolicy.objects.get_or_create(group=group)
    return policy


def effective_values(policy: GroupWithdrawalPolicy | None) -> dict:
    """Merge the group policy over platform defaults (``None`` inherits)."""
    return {
        "auto_approve_limit": getattr(policy, "auto_approve_limit", None)
        or DEFAULT_AUTO_APPROVE_LIMIT,
        "max_withdrawal_limit": getattr(policy, "max_withdrawal_limit", None) or DEFAULT_MAX_WITHDRAWAL_LIMIT,
        "min_withdrawal_amount": getattr(policy, "min_withdrawal_amount", None) or DEFAULT_MIN_WITHDRAWAL_AMOUNT,
        "weekly_withdrawal_limit": getattr(policy, "weekly_withdrawal_limit", None),
        "weekly_withdrawal_count": getattr(policy, "weekly_withdrawal_count", None),
        "monthly_withdrawal_limit": getattr(policy, "monthly_withdrawal_limit", None),
        "min_retained_ratio": getattr(policy, "min_retained_ratio", None) or DEFAULT_MIN_RETAINED_RATIO,
        "review_on_outstanding_loan": bool(getattr(policy, "review_on_outstanding_loan", False)),
        "review_on_outstanding_penalty": bool(getattr(policy, "review_on_outstanding_penalty", False)),
        "review_levels": getattr(policy, "review_levels", GroupWithdrawalPolicy.REVIEW_SINGLE),
        "reviewer_role": getattr(policy, "reviewer_role", GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT) or GroupWithdrawalPolicy.REVIEWER_ROLE_DEFAULT,
        "policy_version": (
            f"group-{policy.pk}-{policy.updated_at.timestamp():.0f}"
            if policy is not None
            else DEFAULT_POLICY_VERSION
        ),
    }


def _member_withdrawal_stats(member, since, statuses):
    """Sum and count of the member's processed withdrawals since ``since``."""
    from accounts.models import WithdrawalRequest

    rows = WithdrawalRequest.objects.filter(
        member=member,
        requested_at__gte=since,
    ).exclude(status__in=statuses)
    total = Decimal("0.00")
    for row in rows.only("amount"):
        total += row.amount
    return total, rows.count()


def _has_conditions(member) -> tuple[bool, bool]:
    """(outstanding_loan, outstanding_penalty) for the member."""
    from loans.models import LoanAccount, LoanPenalty

    has_loan = LoanAccount.objects.filter(
        member=member,
        outstanding_principal__gt=0,
        status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED, LoanAccount.DEFAULTED],
    ).exists()
    has_penalty = LoanPenalty.objects.filter(
        loan__member=member,
        is_paid=False,
    ).exists()
    return has_loan, has_penalty


def evaluate_withdrawal(
    *,
    member,
    account,
    group,
    amount,
    available_balance,
    policy: GroupWithdrawalPolicy | None = None,
) -> PolicyDecision:
    """Decide AUTO_APPROVED / MANUAL_REVIEW / REJECTED for one withdrawal.

    ``available_balance`` must already exclude every other active reservation
    (the reservation logic lives in :mod:`governance.withdrawals` under the
    account row lock, so this function stays a pure, testable decision).
    """
    amount = Decimal(str(amount))
    available_balance = Decimal(str(available_balance))
    values = effective_values(policy)

    reject = []
    review = []
    passed = []

    # 1. Member / account validation -----------------------------------------
    if not member.is_verified:
        return PolicyDecision(
            Decision.REJECTED, "Withdrawals require a verified account.",
            code=ApprovalError.KYC_REQUIRED,
            failed_rules=[{"code": ApprovalError.KYC_REQUIRED, "message": "Account is not KYC verified."}],
            policy_version=values["policy_version"],
        )
    if not (getattr(member, "is_active", True) if hasattr(member, "is_active") else True):
        return PolicyDecision(
            Decision.REJECTED, "Member account is not active.",
            code=ApprovalError.MEMBER_NOT_ACTIVE,
            failed_rules=[{"code": ApprovalError.MEMBER_NOT_ACTIVE, "message": "Member not active."}],
            policy_version=values["policy_version"],
        )

    # 2. Amount sanity --------------------------------------------------------
    if amount <= 0:
        return PolicyDecision(
            Decision.REJECTED, "Amount must be positive.",
            code=ApprovalError.INVALID_AMOUNT,
            failed_rules=[{"code": ApprovalError.INVALID_AMOUNT, "message": "Amount must be positive."}],
            policy_version=values["policy_version"],
        )
    passed.append("amount_positive")

    # 3. Minimum / maximum ----------------------------------------------------
    minimum = values["min_withdrawal_amount"]
    if minimum and amount < minimum:
        reject.append(
            ("WITHDRAWAL_LIMIT_EXCEEDED",
             f"Below the minimum withdrawal amount of {minimum}.")
        )

    maximum = values["max_withdrawal_limit"]
    if maximum and amount > maximum:
        reject.append(
            (ApprovalError.WITHDRAWAL_LIMIT_EXCEEDED,
             f"Exceeds the maximum withdrawal limit of {maximum}.")
        )
    if not reject:
        passed.append("within_withdrawal_bounds")

    # 4. Sufficient available balance (already includes reservations) ---------
    if available_balance < amount:
        reject.append(
            (ApprovalError.INSUFFICIENT_AVAILABLE_BALANCE,
             "Insufficient available balance.")
        )
    else:
        passed.append("available_balance_sufficient")

    # 5. Minimum retained balance ---------------------------------------------
    balance = Decimal(str(getattr(account, "balance", "0") or "0"))
    retained_ratio = values["min_retained_ratio"]
    if retained_ratio and balance > 0:
        retained_after = balance - amount
        if retained_after < (balance * retained_ratio):
            reject.append(
                (ApprovalError.MINIMUM_RETAINED_BALANCE_VIOLATION,
                 "The withdrawal would breach the minimum retained balance.")
            )
        else:
            passed.append("retained_balance_preserved")
    else:
        passed.append("retained_balance_preserved")

    if reject:
        code, message = reject[0]
        return PolicyDecision(
            Decision.REJECTED,
            message,
            code=code,
            rules_passed=passed,
            failed_rules=[{"code": code, "message": message}],
            policy_version=values["policy_version"],
        )

    # 6. Automatic threshold ------------------------------------------------
    auto_limit = values["auto_approve_limit"]
    if auto_limit is not None and amount > auto_limit:
        review.append(
            (ApprovalError.MANUAL_REVIEW_REQUIRED,
             "Amount exceeds the automatic withdrawal threshold.")
        )
    else:
        passed.append("within_auto_approval_limit")

    # 7. Frequency -----------------------------------------------------------
    now = timezone.now()
    week = now - timedelta(days=7)
    month = now - timedelta(days=30)
    done = ["FAILED", "REJECTED", "CANCELLED"]
    weekly_total, weekly_count = _member_withdrawal_stats(member, week, done)
    monthly_total, _monthly_count = _member_withdrawal_stats(member, month, done)

    weekly_limit = values["weekly_withdrawal_limit"]
    if weekly_limit and (weekly_total + amount) > weekly_limit:
        review.append(
            (ApprovalError.WITHDRAWAL_FREQUENCY_EXCEEDED,
             "Weekly withdrawal limit would be exceeded.")
        )
    else:
        passed.append("weekly_limit_respected")

    count_limit = values["weekly_withdrawal_count"]
    if count_limit and (weekly_count + 1) > count_limit:
        review.append(
            (ApprovalError.WITHDRAWAL_FREQUENCY_EXCEEDED,
             "Weekly withdrawal frequency would be exceeded.")
        )
    else:
        passed.append("weekly_frequency_respected")

    monthly_limit = values["monthly_withdrawal_limit"]
    if monthly_limit and (monthly_total + amount) > monthly_limit:
        review.append(
            (ApprovalError.WITHDRAWAL_FREQUENCY_EXCEEDED,
             "Monthly withdrawal limit would be exceeded.")
        )
    else:
        passed.append("monthly_limit_respected")

    # 8. Risk / context flags -------------------------------------------------
    if values.get("review_on_outstanding_loan"):
        has_loan, _has_penalty = _has_conditions(member)
        if has_loan:
            review.append(
                (ApprovalError.MANUAL_REVIEW_REQUIRED,
                 "Member has an outstanding loan.")
            )
    if values.get("review_on_outstanding_penalty"):
        _has_loan, has_penalty = _has_conditions(member)
        if has_penalty:
            review.append(
                (ApprovalError.MANUAL_REVIEW_REQUIRED,
                 "Member has an unpaid loan penalty.")
            )

    if review:
        code, message = review[0]
        return PolicyDecision(
            Decision.MANUAL_REVIEW,
            message,
            code=code,
            rules_passed=passed,
            failed_rules=[{"code": code, "message": message}],
            policy_version=values["policy_version"],
            required_level=Decision.MANUAL_REVIEW,
            required_role=values["reviewer_role"],
            review_levels=values["review_levels"],
            metadata={"manual_review_rules": [r[1] for r in review]},
        )

    return PolicyDecision(
        Decision.AUTO_APPROVED,
        "Withdrawal satisfied configured group policy.",
        code="",
        rules_passed=passed,
        failed_rules=[],
        policy_version=values["policy_version"],
        required_level=Decision.AUTO_APPROVED,
        required_role="",
        review_levels=values["review_levels"],
    )