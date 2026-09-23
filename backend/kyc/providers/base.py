"""Provider abstraction for identity verification.

KYC Service -> IdentityVerificationProvider -> Authorized verification service

Concrete adapters (e.g. an authorized NIDA integration) implement this interface.
The KYC engine only ever depends on this module, so providers are swappable.
No provider in this repository scrapes or reverse-engineers any external site.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderOutcome:
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    ERROR = "ERROR"


@dataclass
class ProviderVerificationResponse:
    """Normalised provider outcome. ``raw`` is transient (never persisted)."""

    outcome: str                      # ProviderOutcome.*
    provider_reference: str = ""
    verified_name: str = ""
    verified_dob: str = ""            # ISO date string
    match: dict = field(default_factory=dict)   # {"full_name": bool, "date_of_birth": bool, "national_id": bool}
    failure_code: str = ""
    failure_reason: str = ""
    raw: dict = field(default_factory=dict)      # NOT stored; diagnostics only


class IdentityVerificationProvider(ABC):
    """Contract every verification adapter must satisfy."""

    provider_id = "abstract"
    vendor = ""

    @abstractmethod
    def verify_identity(self, *, national_id: str, full_name: str, date_of_birth: str) -> ProviderVerificationResponse:
        """Submit one identity verification and return the authoritative result."""

    def check_verification(self, provider_reference: str) -> ProviderVerificationResponse | None:
        """Poll a previously submitted verification (async providers)."""
        return None

    def is_available(self) -> bool:
        return True