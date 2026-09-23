"""Idempotently materialise KYC profiles for every Member.

Existing members verified through the legacy manual pipeline (``Member.is_verified
== True``) are mapped into explicit, audited ``VERIFIED`` / ``LEVEL_1`` profiles
via ``kyc.services.sync_from_member`` so the financial engines see one
authoritative verification state. Members that were never verified stay
``NOT_STARTED`` (a profile row is still created so the member-facing KYC UI can
render without a distinct "no profile" path).

Run: ``python manage.py backfill_kyc_profiles`` (safe to re-run).
"""
from django.core.management.base import BaseCommand

from kyc import services as kyc_services
from kyc.models import KYCProfile
from members.models import Member


class Command(BaseCommand):
    help = "Idempotently backfill KYC profiles from existing Member verification state."

    def handle(self, *args, **options):
        synced = 0
        untouched = 0
        for member in Member.objects.order_by("membership_number").iterator():
            profile, _ = KYCProfile.objects.get_or_create(member=member)
            if profile.status == "VERIFIED":
                untouched += 1
                continue
            if member.is_verified:
                kyc_services.sync_from_member(member)
                synced += 1
            else:
                untouched += 1

        self.stdout.write(
            f"KYC backfill complete: {synced} member(s) synced to VERIFIED (LEVEL_1); "
            f"{untouched} already VERIFIED or remain NOT_STARTED."
        )