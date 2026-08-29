from rest_framework.test import APIClient
from django.test import TestCase

from members.models import Member
from users.models import User
from .models import (
    GroupContribution,
    GroupInvitation,
    GroupMembership,
    GroupShare,
    VikobaGroup,
)


class GroupAPITest(TestCase):
    """Groups feature: open creation/hisa, invitations and contributions."""

    def setUp(self):
        self.client = APIClient()
        self.creator = self._member("creator@example.com", "+254700000001", verified=True)
        self.friend = self._member("friend@example.com", "+254700000002", verified=True)
        self.unverified = self._member(
            "unverified@example.com", "+254700000003", verified=False
        )

    def _member(self, email, phone, verified):
        user = User.objects.create_user(
            email=email,
            username=email.split("@")[0],
            password="test-password-123",
            role=User.MEMBER,
            email_verified=verified,
        )
        member = Member.objects.create(
            user=user,
            first_name=email.split("@")[0].title(),
            last_name="Test",
            phone_number=phone,
            email=email,
            registration_source=Member.RegistrationSource.ADMIN,
            is_verified=verified,
        )
        return member

    def force(self, user):
        self.client.force_authenticate(user)

    def create_group(self, name="Jua Kali"):
        self.force(self.creator.user)
        response = self.client.post(
            "/api/v1/groups",
            {"name": name, "area": "Nairobi", "description": "Test group"},
            format="json",
        )
        return response

    def test_unverified_member_can_create_group(self):
        self.force(self.unverified.user)
        response = self.client.post("/api/v1/groups", {"name": "No"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            GroupMembership.objects.filter(
                group_id=response.data["id"],
                member=self.unverified,
                role=GroupMembership.Role.CHAIRPERSON,
            ).exists()
        )

    def test_unlinked_staff_cannot_create_group(self):
        staff = User.objects.create_user(
            email="staff.group@example.com",
            username="staff-group",
            password="test-password-123",
            role=User.ADMIN,
        )
        self.force(staff)
        response = self.client.post("/api/v1/groups", {"name": "No"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_verified_member_creates_group_and_becomes_chairperson(self):
        response = self.create_group()
        self.assertEqual(response.status_code, 201)
        group = VikobaGroup.objects.get(pk=response.data["id"])
        membership = group.memberships.get(member=self.creator)
        self.assertEqual(membership.role, GroupMembership.Role.CHAIRPERSON)
        self.assertEqual(response.data["member_count"], 1)

    def test_invite_and_join_flow(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        invite = self.client.post(
            f"/api/v1/groups/{group_id}/invite",
            {"email": "friend@example.com"},
            format="json",
        )
        self.assertEqual(invite.status_code, 201)
        token = invite.data["token"]

        self.force(self.friend.user)
        join = self.client.post(
            f"/api/v1/groups/{group_id}/join", {"token": token}, format="json"
        )
        self.assertEqual(join.status_code, 200)
        self.assertTrue(
            GroupMembership.objects.filter(group_id=group_id, member=self.friend).exists()
        )

        invitation = GroupInvitation.objects.get(token=token)
        self.assertEqual(invitation.status, GroupInvitation.Status.ACCEPTED)

        detail = self.client.get(f"/api/v1/groups/{group_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["member_count"], 2)

    def test_unverified_member_can_enter_group_and_buy_hisa(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        invite = self.client.post(
            f"/api/v1/groups/{group_id}/invite",
            {"email": "unverified@example.com"},
            format="json",
        )
        self.assertEqual(invite.status_code, 201)

        # The invitee does not need verification to enter the group.
        self.force(self.unverified.user)
        join = self.client.post(
            f"/api/v1/groups/{group_id}/join",
            {"token": invite.data["token"]},
            format="json",
        )
        self.assertEqual(join.status_code, 200)

        # Buying hisa is open to any group member without verification.
        shares = self.client.post(
            f"/api/v1/groups/{group_id}/shares",
            {"quantity": 2, "amount_paid": "2000.00"},
            format="json",
        )
        self.assertEqual(shares.status_code, 201)
        membership = GroupMembership.objects.get(group_id=group_id, member=self.unverified)
        self.assertEqual(membership.shares_count, 2)

        # Contributing is open to any group member (confirmation is manual).
        contribution = self.client.post(
            f"/api/v1/groups/{group_id}/contributions",
            {"amount": "1000.00", "month": "2026-08"},
            format="json",
        )
        self.assertEqual(contribution.status_code, 201)

    def test_buy_hisa_increments_membership_shares(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        shares = self.client.post(
            f"/api/v1/groups/{group_id}/shares",
            {"quantity": 5, "amount_paid": "5000.00"},
            format="json",
        )
        self.assertEqual(shares.status_code, 201)

        membership = GroupMembership.objects.get(group_id=group_id, member=self.creator)
        self.assertEqual(membership.shares_count, 5)

    def test_staff_confirms_contribution(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        contribution = self.client.post(
            f"/api/v1/groups/{group_id}/contributions",
            {"amount": "2500.00", "month": "2026-08"},
            format="json",
        )
        self.assertEqual(contribution.status_code, 201)

        staff = User.objects.create_user(
            email="staff.confirm@example.com",
            username="staff-confirm",
            password="test-password-123",
            role=User.FINANCE,
        )
        self.force(staff)
        decision = self.client.post(
            f"/api/v1/groups/{group_id}/contributions/{contribution.data['id']}/confirm",
            {"status": "CONFIRMED"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.data["status"], GroupContribution.Status.CONFIRMED)

    def test_member_cannot_confirm_contributions(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        contribution = self.client.post(
            f"/api/v1/groups/{group_id}/contributions",
            {"amount": "100.00", "month": "2026-08"},
            format="json",
        )

        self.force(self.friend.user)
        decision = self.client.post(
            f"/api/v1/groups/{group_id}/contributions/{contribution.data['id']}/confirm",
            {"status": "CONFIRMED"},
            format="json",
        )
        self.assertEqual(decision.status_code, 403)

    def test_membership_required_for_group_actions(self):
        response = self.create_group()
        group_id = response.data["id"]

        # Friend is not a member yet: cannot invite or contribute.
        self.force(self.friend.user)
        invite = self.client.post(
            f"/api/v1/groups/{group_id}/invite",
            {"email": "someone@example.com"},
            format="json",
        )
        self.assertEqual(invite.status_code, 403)

    def test_pending_invitations_visible_to_the_invitee(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        self.client.post(
            f"/api/v1/groups/{group_id}/invite",
            {"email": "friend@example.com"},
            format="json",
        )

        self.force(self.friend.user)
        pending = self.client.get("/api/v1/groups/invitations/pending")
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.data[0]["group_id"], group_id)
        self.assertEqual(pending.data[0]["status"], "PENDING")

    def test_accept_invite_by_token_alone(self):
        response = self.create_group()
        group_id = response.data["id"]

        self.force(self.creator.user)
        invite = self.client.post(
            f"/api/v1/groups/{group_id}/invite",
            {"email": "friend@example.com"},
            format="json",
        )
        self.assertEqual(invite.status_code, 201)

        self.force(self.friend.user)
        accept = self.client.post(
            "/api/v1/groups/accept-invite",
            {"token": invite.data["token"]},
            format="json",
        )
        self.assertEqual(accept.status_code, 200)
        self.assertEqual(accept.data["id"], group_id)
        self.assertTrue(
            GroupMembership.objects.filter(group_id=group_id, member=self.friend).exists()
        )


class GroupLimitsAndCommitteeTest(TestCase):
    """Group creation limits, the dashboard summary and the elected committee."""

    def setUp(self):
        self.client = APIClient()
        self.creator = self._member("boss@example.com", "+254700000101", verified=True)
        self.alice = self._member("alice@example.com", "+254700000102", verified=True)
        self.bob = self._member("bob@example.com", "+254700000103", verified=True)
        self.unverified = self._member(
            "unv@example.com", "+254700000104", verified=False
        )

    def _member(self, email, phone, verified):
        user = User.objects.create_user(
            email=email,
            username=email.split("@")[0],
            password="test-password-123",
            role=User.MEMBER,
            email_verified=verified,
        )
        return Member.objects.create(
            user=user,
            first_name=email.split("@")[0].title(),
            last_name="Test",
            phone_number=phone,
            email=email,
            registration_source=Member.RegistrationSource.ADMIN,
            is_verified=verified,
        )

    def force(self, user):
        self.client.force_authenticate(user)

    def make_group(self, by, name="G"):
        self.force(by.user)
        return self.client.post(
            "/api/v1/groups", {"name": name, "area": "Area", "region": "Region", "country": "Country"}, format="json"
        )

    def test_unverified_limited_to_one_group(self):
        first = self.make_group(self.unverified, "One")
        self.assertEqual(first.status_code, 201)
        second = self.make_group(self.unverified, "Two")
        self.assertEqual(second.status_code, 400)

    def test_verified_can_create_up_to_three_groups(self):
        for name in ["A", "B", "C"]:
            response = self.make_group(self.creator, name)
            self.assertEqual(response.status_code, 201)
        fourth = self.make_group(self.creator, "D")
        self.assertEqual(fourth.status_code, 400)

    def test_location_fields_saved_on_create(self):
        response = self.make_group(self.creator, "Kinondoni")
        self.assertEqual(response.status_code, 201)
        group = VikobaGroup.objects.get(pk=response.data["id"])
        self.assertEqual(group.region, "Region")
        self.assertEqual(group.country, "Country")

    def test_dashboard_summary_aggregates(self):
        response = self.make_group(self.creator, "Hisa")
        group_id = response.data["id"]
        GroupMembership.objects.get_or_create(
            group_id=group_id, member=self.creator,
            defaults={"role": GroupMembership.Role.CHAIRPERSON},
        )
        membership = GroupMembership.objects.get(group_id=group_id, member=self.creator)
        membership.shares_count = 3
        membership.save(update_fields=["shares_count"])
        GroupShare.objects.create(
            group_id=group_id, member=self.creator, quantity=3, amount_paid="300.00"
        )
        GroupContribution.objects.create(
            group_id=group_id, member=self.creator, amount="2000.00",
            month="2026-08", status=GroupContribution.Status.CONFIRMED,
        )
        GroupContribution.objects.create(
            group_id=group_id, member=self.creator, amount="500.00",
            month="2026-09", status=GroupContribution.Status.PENDING,
        )

        self.force(self.creator.user)
        summary = self.client.get("/api/v1/groups/me/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["total_shares"], 3)
        self.assertEqual(summary.data["hisa_value"], 100.0)
        self.assertEqual(summary.data["contributed_total"], 2000.0)
        self.assertEqual(summary.data["contributed_pending"], 500.0)

    def test_committee_election_flow(self):
        response = self.make_group(self.creator, "Committee")
        group_id = response.data["id"]
        GroupMembership.objects.create(group_id=group_id, member=self.alice)
        GroupMembership.objects.create(group_id=group_id, member=self.bob)

        # Alice (verified) declares interest for treasurer; Bob votes for her.
        self.force(self.alice.user)
        declare = self.client.post(
            f"/api/v1/groups/{group_id}/committee/declare",
            {"role": "TREASURER"},
            format="json",
        )
        self.assertEqual(declare.status_code, 201)

        self.force(self.bob.user)
        vote = self.client.post(
            f"/api/v1/groups/{group_id}/committee/vote",
            {"role": "TREASURER", "candidate_id": str(self.alice.pk)},
            format="json",
        )
        self.assertEqual(vote.status_code, 200)

        # The chairperson confirms the winner after the vote.
        self.force(self.creator.user)
        committee = self.client.get(f"/api/v1/groups/{group_id}/committee")
        self.assertEqual(committee.status_code, 200)
        treasurer_race = committee.data["roles"]["TREASURER"]
        self.assertEqual(len(treasurer_race["candidates"]), 1)
        self.assertEqual(treasurer_race["candidates"][0]["votes"], 1)

        close = self.client.post(
            f"/api/v1/groups/{group_id}/committee/close",
            {"role": "TREASURER"},
            format="json",
        )
        self.assertEqual(close.status_code, 200)
        self.assertEqual(close.data["member"]["membership_number"], self.alice.membership_number)

        membership = GroupMembership.objects.get(group_id=group_id, member=self.alice)
        self.assertEqual(membership.role, GroupMembership.Role.TREASURER)

    def test_unverified_cannot_declare_and_only_chairperson_closes(self):
        response = self.make_group(self.creator, "Rules")
        group_id = response.data["id"]
        GroupMembership.objects.create(group_id=group_id, member=self.unverified)
        GroupMembership.objects.create(group_id=group_id, member=self.alice)

        self.force(self.unverified.user)
        declare = self.client.post(
            f"/api/v1/groups/{group_id}/committee/declare",
            {"role": "SECRETARY"},
            format="json",
        )
        self.assertEqual(declare.status_code, 400)

        # Alice could declare, but she is not the chairperson: closing must fail.
        self.force(self.alice.user)
        declare = self.client.post(
            f"/api/v1/groups/{group_id}/committee/declare",
            {"role": "SECRETARY"},
            format="json",
        )
        self.assertEqual(declare.status_code, 201)
        close = self.client.post(
            f"/api/v1/groups/{group_id}/committee/close",
            {"role": "SECRETARY"},
            format="json",
        )
        self.assertEqual(close.status_code, 403)