import secrets
from datetime import timedelta
from string import ascii_letters, digits

from django.db import models
from django.utils import timezone

from members.models import Member


def _invite_token():
    alphabet = ascii_letters + digits
    return "".join(secrets.choice(alphabet) for _ in range(40))


class VikobaGroup(models.Model):
    """A subgroup inside the platform: members join, buy hisa and contribute."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    name = models.CharField(max_length=120)
    area = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        related_name="groups_created",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    """Links a member to a group (with role) and tracks their hisa units."""

    class Role(models.TextChoices):
        MEMBER = "MEMBER", "Member"
        CHAIRPERSON = "CHAIRPERSON", "Chairperson"
        SECRETARY = "SECRETARY", "Secretary"
        TREASURER = "TREASURER", "Treasurer"

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    shares_count = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "member"],
                name="unique_group_member",
            )
        ]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.member} in {self.group}"


class GroupInvitation(models.Model):
    """Email invitation to join a group. Accepting requires a registered member."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"
        EXPIRED = "EXPIRED", "Expired"

    TTL_DAYS = 14

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    invited_by = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    token = models.CharField(max_length=40, unique=True, default=_invite_token)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=self.TTL_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"{self.email} -> {self.group}"


class GroupShare(models.Model):
    """Hisa purchase record within a group."""

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_shares",
    )
    quantity = models.PositiveIntegerField()
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quantity} hisa by {self.member} in {self.group}"


class GroupContribution(models.Model):
    """Member contribution to the group; confirmed manually by staff."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_contributions",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.CharField(
        max_length=7,
        help_text="Contribution month, format YYYY-MM",
    )
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    confirmed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_contributions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.amount} by {self.member} in {self.group}"


class ShareOut(models.Model):
    """A VSLA cycle-end share-out declared for a group."""

    class Status(models.TextChoices):
        DECLARED = "DECLARED", "Declared"
        PAID = "PAID", "Paid"

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="share_outs",
    )
    cycle_label = models.CharField(max_length=80)
    declared_at = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DECLARED,
    )
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="declared_share_outs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-declared_at"]
        unique_together = ("group", "cycle_label")

    def __str__(self):
        return f"{self.group} - {self.cycle_label}"


class MemberShareOut(models.Model):
    """One member's entitlement under a share-out."""

    share_out = models.ForeignKey(
        ShareOut,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="share_out_entries",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paid_share_outs",
    )

    class Meta:
        ordering = ["-id"]
        unique_together = ("share_out", "member")

    def __str__(self):
        return f"{self.member} - {self.amount}"


class ElectedRole(models.TextChoices):
    """Committee positions chosen by member vote (chairperson is the creator)."""

    TREASURER = "TREASURER", "Treasurer"
    SECRETARY = "SECRETARY", "Secretary"


class GroupRoleCandidate(models.Model):
    """A verified member who declared interest to run for an elected role."""

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="role_candidates",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_role_candidacies",
    )
    role = models.CharField(max_length=20, choices=ElectedRole.choices)
    declared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["declared_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "member", "role"],
                name="unique_group_candidate_role",
            )
        ]

    def __str__(self):
        return f"{self.member} for {self.role} in {self.group}"


class GroupRoleVote(models.Model):
    """One member's vote for a candidate standing for an elected role."""

    group = models.ForeignKey(
        VikobaGroup,
        on_delete=models.CASCADE,
        related_name="role_votes",
    )
    voter = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_role_votes_cast",
    )
    candidate = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="group_role_votes_received",
    )
    role = models.CharField(max_length=20, choices=ElectedRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "role", "voter"],
                name="unique_group_role_voter",
            )
        ]

    def __str__(self):
        return f"{self.voter} votes {self.candidate} for {self.role}"