"""Capability-based provider registry."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from app.integrations.errors import NormalizedIntegrationError, ProviderNotRegisteredError
from app.integrations.models import ProviderCapability


class IntegrationRegistry:
    """Registers providers by capability so services never depend on vendor classes."""

    def __init__(self):
        self._providers: MutableMapping[ProviderCapability, Any] = {}

    def register(self, capability: ProviderCapability, provider: Any) -> None:
        self._providers[capability] = provider

    def get(self, capability: ProviderCapability) -> Any:
        provider = self._providers.get(capability)
        if provider is None:
            raise ProviderNotRegisteredError(
                NormalizedIntegrationError(
                    code="MAPPING_NOT_FOUND",
                    category="mapping",
                    provider_key="registry",
                    retryable=False,
                    user_facing_message="Integration provider is not configured.",
                    operator_message=(
                        f"No provider registered for capability={capability.value}"
                    ),
                )
            )
        return provider


registry = IntegrationRegistry()


def register_provider(capability: ProviderCapability, provider: Any) -> None:
    registry.register(capability, provider)


def get_provider(capability: ProviderCapability) -> Any:
    return registry.get(capability)


def register_default_providers() -> None:
    """Wire up default runtime adapters."""
    from app.integrations.providers.fake_samsara import FakeSamsaraProvider
    from app.integrations.providers.samsara import SamsaraProvider
    from app.integrations.providers.twilio import TwilioMessagingProvider
    from app.core.config import settings

    telematics_dashcam_provider: Any
    if settings.APP_ENV in {"local", "test"} and not settings.SAMSARA_API_KEY.strip():
        telematics_dashcam_provider = FakeSamsaraProvider()
    else:
        telematics_dashcam_provider = SamsaraProvider()

    twilio = TwilioMessagingProvider()

    register_provider(ProviderCapability.TELEMATICS, telematics_dashcam_provider)
    register_provider(ProviderCapability.DASHCAM, telematics_dashcam_provider)
    register_provider(ProviderCapability.MESSAGING, twilio)
