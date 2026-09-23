"""Per-group lending policy resolution and group capacity enforcement."""

from decimal import Decimal

from django.conf import settings
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce

from accounts.models import SavingsAccount
from groups.models import GroupMembership

from .calculations import _money
from .models import GroupLoanPolicy, LoanAccount, LoanApplication

ZERO = Decimal("0.00")


def _default_penalty_rate():
    return Decimal(str(getattr(settings, "LOAN_PENALTY_RATE", "0.00")))


def _default_penalty_grace_days():
    return int(getattr(settings, "LOAN_PENALTY_GRACE_DAYS", 7))


def get_or_create_policy(group):
    """Fetch the group policy, creating the default (all-inherit) row lazily."""
    if group is None:
        return None
    policy, _created = GroupLoanPolicy.objects.get_or_create(group=group)
    return policy


def effective_values(group, product):
    """Blend a group's loan policy over the product defaults.

    A policy field set to ``None`` means "inherit the product / platform
    default", so a fresh group behaves exactly like the product configuration.
    """
    policy = get_or_create_policy(group)

    def _pick(policy_field, product_field):
        value = getattr(policy, policy_field) if policy else None
        if value is None:
            value = getattr(product, product_field)
        return value

    return {
        "max_amount": _pick("max_amount", "max_amount"),
        "max_term_months": _pick("max_term_months", "max_term_months"),
        "multiplier": _pick("multiplier", "multiplier"),
        "interest_rate": _pick("interest_rate", "interest_rate"),
        "interest_type": _pick("interest_type", "interest_type"),
        "requires_guarantors": _pick("requires_guarantors", "requires_guarantors"),
        "penalty_rate": (
            (Decimal(policy.penalty_rate) if policy and policy.penalty_rate is not None else None)
            or _default_penalty_rate()
        ),
        "penalty_grace_days": (
            (policy.penalty_grace_days if policy and policy.penalty_grace_days is not None else None)
            or _default_penalty_grace_days()
        ),
        "group_capacity_enabled": bool(policy.group_capacity_enabled) if policy else False,
        "kyc_level_required": (
            (policy.kyc_level_required if policy and policy.kyc_level_required else None)
            or _default_kyc_level()
        ),
    }


def _default_kyc_level():
    return str(getattr(settings, "KYC_REQUIRED_LEVEL", "LEVEL_1"))


def group_member_ids(group):
    return list(
        GroupMembership.objects.filter(group=group, is_active=True).values_list("member_id", flat=True)
    )


def group_capacity(group):
    """How much group lending capacity remains.

    Defined as aggregate member savings minus aggregate outstanding principal of
    active loans minus approved-but-not-yet-disbursed application amounts. An
    approval *reserves* its principal so concurrent approvals inside the group
    cannot exceed the cap before any money even moves.
    """
    member_ids = group_member_ids(group)
    savings = (
        SavingsAccount.objects.filter(member_id__in=member_ids).aggregate(total=Sum("balance")).get("total")
        or ZERO
    )
    outstanding = (
        LoanAccount.objects.filter(
            member_id__in=member_ids,
            status__in=[LoanAccount.APPROVED, LoanAccount.DISBURSED, LoanAccount.DEFAULTED],
        ).aggregate(total=Sum("outstanding_principal")).get("total")
        or ZERO
    )
    reserved = (
        LoanApplication.objects.filter(
            member_id__in=member_ids,
            status=LoanApplication.Status.APPROVED,
        )
        .annotate(
            pending=Coalesce("approved_amount", "requested_amount", output_field=DecimalField())
        )
        .aggregate(total=Sum("pending")).get("total")
        or ZERO
    )
    committed = _money(Decimal(outstanding) + Decimal(reserved))
    return {
        "members_count": len(member_ids),
        "total_savings": savings,
        "total_outstanding": outstanding,
        "total_reserved": reserved,
        "remaining_capacity": savings - committed,
    }


def capacity_available(group, requested_amount):
    """True when the group still has room for another loan of this size."""
    if group is None:
        return True, None
    capacity = group_capacity(group)
    ok = capacity["remaining_capacity"] >= requested_amount
    return ok, capacity