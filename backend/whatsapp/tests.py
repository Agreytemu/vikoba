from django.test import TestCase
from rest_framework.test import APIClient

from members.models import Member
from users.models import User
from groups.models import GroupContribution, VikobaGroup
from .models import WhatsAppSession


class WhatsAppGatewayTest(TestCase):
    """Paired-device gateway: role guards and graceful bridge-off behaviour."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="admin.whatsapp@example.com",
            username="admin-whatsapp",
            password="test-password-123",
            role=User.ADMIN,
        )
        self.creator = self._member("chair@example.com", "+254700000011", verified=True)

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

    def create_group(self):
        self.force(self.creator.user)
        response = self.client.post(
            "/api/v1/groups",
            {"name": "WhatsApp Chama", "area": "Nairobi"},
            format="json",
        )
        return response.data["id"]

    def test_staff_can_create_and_list_admin_device(self):
        self.force(self.staff)
        create = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "ADMIN", "display_name": "Office phone"},
            format="json",
        )
        self.assertEqual(create.status_code, 201)
        session_id = create.data["session_id"]
        self.assertTrue(session_id.startswith("admin-"))

        retrieved = self.client.get("/api/v1/whatsapp/sessions/")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(len(retrieved.data), 1)

        detail = self.client.get(f"/api/v1/whatsapp/sessions/{session_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["status"], "disconnected")

    def test_member_cannot_create_admin_device(self):
        self.force(self.creator.user)
        response = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "ADMIN"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_chair_member_cannot_pair_group_device(self):
        self.force(self.staff)
        group_id = self.create_group()
        other = self._member("other@example.com", "+254700000012", verified=False)
        self.force(other.user)
        response = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_chairperson_can_pair_group_device(self):
        group_id = self.create_group()
        self.force(self.creator.user)
        response = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            WhatsAppSession.objects.filter(
                owner_type="CHAIR", group_id=group_id
            ).exists()
        )

    def test_forced_secondary_create_returns_existing_group_device(self):
        group_id = self.create_group()
        self.force(self.creator.user)
        first = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        second = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["session_id"], second.data["session_id"])

    def test_pairing_code_without_bridge_errors_gracefully(self):
        self.force(self.staff)
        create = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "ADMIN", "display_name": "Office phone"},
            format="json",
        )
        session_id = create.data["session_id"]
        response = self.client.post(
            f"/api/v1/whatsapp/sessions/{session_id}/pair/",
            {"phone": "+254700000001"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("error"), "bridge_not_configured")

    def test_non_manager_cannot_pair_device(self):
        self.force(self.staff)
        create = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "ADMIN", "display_name": "Office phone"},
            format="json",
        )
        other = self._member("other@example.com", "+254700000012", verified=False)
        self.force(other.user)
        response = self.client.post(
            f"/api/v1/whatsapp/sessions/{create.data['session_id']}/pair/",
            {"phone": "+254700000001"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_manage_another_staff_admin_device(self):
        self.force(self.staff)
        create = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "ADMIN", "display_name": "Office phone"},
            format="json",
        )
        session_id = create.data["session_id"]
        other_staff = User.objects.create_user(
            email="admin2.whatsapp@example.com",
            username="admin2-whatsapp",
            password="test-password-123",
            role=User.ADMIN,
        )
        self.force(other_staff)
        listed = self.client.get("/api/v1/whatsapp/sessions/")
        row = next((s for s in listed.data if s["session_id"] == session_id), None)
        self.assertIsNotNone(row)
        self.assertFalse(row["can_manage"])
        pair = self.client.post(
            f"/api/v1/whatsapp/sessions/{session_id}/pair/",
            {"phone": "+254700000001"},
            format="json",
        )
        self.assertEqual(pair.status_code, 403)

    def test_staff_sees_chair_device_read_only(self):
        group_id = self.create_group()
        self.force(self.creator.user)
        chair_device = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        self.assertEqual(chair_device.status_code, 201)

        self.force(self.staff)
        listed = self.client.get("/api/v1/whatsapp/sessions/")
        row = next(
            (s for s in listed.data if s["session_id"] == chair_device.data["session_id"]),
            None,
        )
        self.assertIsNotNone(row)
        self.assertFalse(row["can_manage"])
        pair = self.client.post(
            f"/api/v1/whatsapp/sessions/{chair_device.data['session_id']}/pair/",
            {"phone": "+254700000001"},
            format="json",
        )
        self.assertEqual(pair.status_code, 403)

    def test_chair_manages_own_group_device(self):
        group_id = self.create_group()
        self.force(self.creator.user)
        chair_device = self.client.post(
            "/api/v1/whatsapp/sessions/",
            {"owner_type": "CHAIR", "group": group_id},
            format="json",
        )
        self.assertEqual(chair_device.status_code, 201)
        semaphore = chair_device.data["session_id"]
        listed = self.client.get("/api/v1/whatsapp/sessions/")
        row = next((s for s in listed.data if s["session_id"] == semaphore), None)
        self.assertIsNotNone(row)
        self.assertTrue(row["can_manage"])
        pair = self.client.post(
            f"/api/v1/whatsapp/sessions/{semaphore}/pair/",
            {"phone": "+254700000001"},
            format="json",
        )
        self.assertEqual(pair.status_code, 400)
        self.assertEqual(pair.data.get("error"), "bridge_not_configured")

    def test_confirmation_still_succeeds_without_bridge(self):
        """Receipt delivery must never block the staff confirmation itself."""
        self.force(self.creator.user)
        group_id = self.create_group()
        contribution = self.client.post(
            f"/api/v1/groups/{group_id}/contributions",
            {"amount": "1000", "month": "2026-08", "reference": "REF-1"},
            format="json",
        )
        contribution_id = contribution.data["id"]

        self.force(self.staff)
        decision = self.client.post(
            f"/api/v1/groups/{group_id}/contributions/{contribution_id}/confirm",
            {"status": "CONFIRMED"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.data["status"], "CONFIRMED")
        saved = GroupContribution.objects.get(pk=contribution_id)
        self.assertEqual(saved.status, "CONFIRMED")
        self.assertEqual(VikobaGroup.objects.get(pk=group_id).name, "WhatsApp Chama")