from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Member, PhoneOTP
from users.models import User


class MemberSelfServiceAPITest(TestCase):
    """Self-service verification pipeline for self-registered members."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="self@example.com",
            username="self-user",
            password="test-password-123",
            role=User.MEMBER,
        )
        self.member = Member.objects.create(
            user=self.user,
            first_name="Jane",
            middle_name="",
            last_name="Doe",
            phone_number="+254700111222",
            email=self.user.email,
            registration_source=Member.RegistrationSource.SELF,
            is_verified=False,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def url(self, name):
        return f"/api/v1/members/me/{name}" if name else "/api/v1/members/me/"

    def test_me_profile_matches_membership(self):
        response = self.client.get(self.url(""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["membership_number"], self.member.membership_number)
        self.assertFalse(response.data["is_verified"])
        self.assertFalse(response.data["verification"]["phone_verified"])

    def test_otp_request_returns_dev_code_in_dev_mode(self):
        response = self.client.post(self.url("request-otp/"), {"phone_number": "+254700111222"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["dev_mode"])
        self.assertEqual(len(response.data["dev_code"]), 6)
        self.assertTrue(PhoneOTP.objects.filter(member=self.member).exists())

    def test_otp_verify_marks_phone_verified(self):
        otp = PhoneOTP.issue(self.member, "+254700111222")
        response = self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+254700111222", "code": otp.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["phone_verified"])

        self.member.refresh_from_db()
        self.assertTrue(self.member.phone_verified)
        self.assertFalse(self.member.is_verified)

    def test_otp_verify_detects_snippe_network(self):
        otp = PhoneOTP.issue(self.member, "+255755123456")  # Vodacom / M-Pesa
        response = self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+255755123456", "code": otp.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone_network"], "mpesa")
        self.member.refresh_from_db()
        self.assertEqual(self.member.phone_network, "mpesa")

    def test_otp_verify_unmapped_number_network_unknown(self):
        otp = PhoneOTP.issue(self.member, "+254700111222")
        response = self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+254700111222", "code": otp.code},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["phone_network"], "unknown")

    def test_member_cannot_reach_full_verification_without_every_step(self):
        """The member is only verified once every step + staff KYC review is done."""
        otp = PhoneOTP.issue(self.member, "+254700111222")
        self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+254700111222", "code": otp.code},
        )
        self.client.post(
            self.url("next-of-kin/"),
            {
                "name": "John Doe",
                "relationship": "Spouse",
                "phone_number": "+254722333444",
                "national_id": "12345678",
            },
        )
        self.client.post(self.url("submit-for-review/"))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_verified)

    def test_submit_review_does_not_verify_without_staff_kyc(self):
        otp = PhoneOTP.issue(self.member, "+254700111222")
        self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+254700111222", "code": otp.code},
        )
        self.client.post(
            self.url("next-of-kin/"),
            {"name": "John Doe", "relationship": "Spouse", "phone_number": "+254722333444"},
        )

        # Member uploads all three KYC documents...
        for doc_type in ("NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"):
            response = self.client.post(
                self.url("kyc-documents/"),
                {"document_type": doc_type, "file": SimpleUploadedFile("doc.pdf", b"pdf-fake", content_type="application/pdf")},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, doc_type)

        self.client.post(self.url("submit-for-review/"))
        self.member.refresh_from_db()
        # ...but remains unverified until staff accepts the documents.
        self.assertFalse(self.member.is_verified)

    def test_staff_verification_of_kyc_documents_completes_pipeline(self):
        otp = PhoneOTP.issue(self.member, "+254700111222")
        self.client.post(
            self.url("verify-otp/"),
            {"phone_number": "+254700111222", "code": otp.code},
        )
        self.client.post(
            self.url("next-of-kin/"),
            {"name": "John Doe", "relationship": "Spouse", "phone_number": "+254722333444"},
        )
        self.client.post(self.url("submit-for-review/"))

        doc_refs = []
        for doc_type in ("NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"):
            response = self.client.post(
                self.url("kyc-documents/"),
                {"document_type": doc_type, "file": SimpleUploadedFile("doc.pdf", b"pdf-fake", content_type="application/pdf")},
                format="multipart",
            )
            doc_refs.append((doc_type, response.data["id"]))

        staff = User.objects.create_user(
            email="staff@example.com",
            username="staff-user",
            password="test-password-123",
            role=User.ADMIN,
        )
        self.client.force_authenticate(staff)
        for _, doc_id in doc_refs:
            response = self.client.post(
                f"/api/v1/members/{self.member.membership_number}/kyc-documents/{doc_id}/verify/"
            )
            self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()
        self.assertTrue(self.member.is_verified)

    def test_unlinked_staff_account_has_no_member(self):
        staff = User.objects.create_user(
            email="staff2@example.com",
            username="staff2-user",
            password="test-password-123",
            role=User.ADMIN,
        )
        self.client.force_authenticate(staff)
        response = self.client.get(self.url(""))
        self.assertEqual(response.status_code, 400)