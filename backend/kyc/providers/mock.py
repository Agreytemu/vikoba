"""Simulated verification provider for development, demos and tests.

This adapter is NOT an authoritative identity source. It implements the
:class:`IdentityVerificationProvider` interface so the whole KYC flow can be
exercised offline, and is only ever active under ``KYC_PROVIDER_MODE=simulated``.

Simulated rules (deterministic and documented):
- identity data is matched against the member profile passed in the call
  (name + date of birth, plus a national-ID sanity check of length >= 8);
- a national ID ending in ``666`` always simulates an identity MISMATCH
  (REJECTED) — used to exercise the rejection path in tests/demo;
- a national ID that is all digits equal to ``0`` repeated (e.g. ``0000000000``)
  simulates a provider outage (ERROR) — used to exercise PROVIDER_ERROR;
- otherwise the verification VERIFIED with a synthetic reference.

Provider references are always prefixed ``SIM-KYC-`` so records are easy to spot
and can never be confused with a real, authoritative verification.
"""
import re
import uuid

from kyc.providers.base import IdentityVerificationProvider, ProviderOutcome, ProviderVerificationResponse


class SimulatedKYCProvider(IdentityVerificationProvider):
    provider_id = "simulated"
    vendor = "VICOBA Simulated Identity"

    def verify_identity(self, *, national_id, full_name, date_of_birth):
        ref = f"SIM-KYC-{uuid.uuid4().hex[:12].upper()}"
        clean_id = (national_id or "").strip().upper()

        if not re.fullmatch(r"[A-Z0-9]{8,20}", clean_id):
            return ProviderVerificationResponse(
                outcome=ProviderOutcome.REJECTED,
                provider_reference=ref,
                failure_code="INVALID_NATIONAL_ID_FORMAT",
                failure_reason="National ID failed format validation.",
                match={"full_name": False, "date_of_birth": False, "national_id": False},
                raw={"rule": "format-check"},
            )

        if clean_id.endswith("666"):
            return ProviderVerificationResponse(
                outcome=ProviderOutcome.REJECTED,
                provider_reference=ref,
                failure_code="IDENTITY_MISMATCH",
                failure_reason="Provided identity does not match the registry record.",
                match={"full_name": True, "date_of_birth": True, "national_id": False},
                raw={"rule": "simulated-mismatch"},
            )

        if set(clean_id) == {"0"}:
            return ProviderVerificationResponse(
                outcome=ProviderOutcome.ERROR,
                provider_reference=ref,
                failure_code="PROVIDER_UNAVAILABLE",
                failure_reason="Verification service temporarily unavailable.",
                raw={"rule": "simulated-outage"},
            )

        return ProviderVerificationResponse(
            outcome=ProviderOutcome.VERIFIED,
            provider_reference=ref,
            verified_name=full_name,
            verified_dob=date_of_birth,
            match={"full_name": True, "date_of_birth": True, "national_id": True},
            raw={"rule": "simulated-success"},
        )

    def is_available(self):
        return True