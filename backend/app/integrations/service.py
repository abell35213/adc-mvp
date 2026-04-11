"""Service accessors for integration capabilities."""

from __future__ import annotations

from typing import cast

from app.integrations.base import (
    DashcamProvider,
    MessagingProvider,
    TelematicsProvider,
    VerifyProvider,
    VoiceProvider,
)
from app.integrations.models import ProviderCapability
from app.integrations.registry import get_provider, register_default_providers, registry


def _ensure_defaults() -> None:
    if not registry._providers:  # noqa: SLF001 - internal singleton bootstrap
        register_default_providers()


def get_telematics_provider() -> TelematicsProvider:
    _ensure_defaults()
    return cast(TelematicsProvider, get_provider(ProviderCapability.TELEMATICS))


def get_dashcam_provider() -> DashcamProvider:
    _ensure_defaults()
    return cast(DashcamProvider, get_provider(ProviderCapability.DASHCAM))


def get_messaging_provider() -> MessagingProvider:
    _ensure_defaults()
    return cast(MessagingProvider, get_provider(ProviderCapability.MESSAGING))


def get_verify_provider() -> VerifyProvider:
    _ensure_defaults()
    return cast(VerifyProvider, get_provider(ProviderCapability.MESSAGING))


def get_voice_provider() -> VoiceProvider:
    _ensure_defaults()
    return cast(VoiceProvider, get_provider(ProviderCapability.MESSAGING))
