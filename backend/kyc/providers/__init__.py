"""Identity verification provider registry.

The rest of the application talks to :func:`get_provider()` / the
:class:`IdentityVerificationProvider` interface only — never to provider-specific
API details. A real authorized NIDA/verification-service adapter is added by
implementing the interface and pointing ``KYC_PROVIDER`` at it.

Fail-closed: with no provider configured (or ``KYC_PROVIDER_MODE=disabled``),
``get_provider`` returns ``None`` and every submission results in a
PROVIDER_ERROR — a member is NEVER marked verified without an authoritative
response from a configured provider.
"""
from django.conf import settings

from kyc.providers.base import IdentityVerificationProvider, ProviderVerificationResponse  # noqa: F401
from kyc.providers.mock import SimulatedKYCProvider  # noqa: F401


def provider_mode() -> str:
    return str(getattr(settings, "KYC_PROVIDER_MODE", "disabled")).lower()


def get_provider() -> IdentityVerificationProvider | None:
    """Resolve the configured provider, or ``None`` when no provider is active.

    Modes:
    - ``disabled``  -> None (submissions fail closed with PROVIDER_ERROR).
    - ``simulated`` -> the built-in SimulatedKYCProvider (dev/demo only; it is
      NOT an authoritative identity source and must not be used with a real
      KYC_REQUIRED_LEVEL of LEVEL_2 in production).
    - ``live``      -> requires ``KYC_PROVIDER`` (dotted path) set explicitly.
    """
    mode = provider_mode()

    if mode == "live":
        path = getattr(settings, "KYC_PROVIDER", "") or ""
        if not path:
            return None
        from django.utils.module_loading import import_string

        try:
            cls = import_string(path)
        except ImportError:
            return None
        return cls()

    if mode == "simulated":
        return SimulatedKYCProvider()

    return None