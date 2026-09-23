"""KYC domain: member identity verification status, request engine and audit.

This app is the authoritative verification layer for member identity. It is
deliberately independent of payments, withdrawals, loans and the finance ledger
— it only produces a trusted ``KYCProfile`` state that those engines may consume
as an eligibility input.

Golden chain (never bypassed):

    MEMBER -> KYC REQUEST -> PROVIDER -> VERIFICATION RESPONSE -> VALIDATION
             -> KYC STATUS -> AUDIT EVENT -> FINANCIAL ELIGIBILITY

The frontend can never set KYC status directly; only the backend verification
process (or an authorised, audited manual reviewer) transitions the profile.
"""
from django.apps import AppConfig


class KYCConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "kyc"
    verbose_name = "KYC & Identity Verification"