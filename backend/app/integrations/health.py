"""Provider health models and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.errors import NormalizedIntegrationError, ProviderHealthError


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    healthy: bool
    details: str = ""


def ensure_healthy(health: ProviderHealth) -> ProviderHealth:
    if not health.healthy:
        raise ProviderHealthError(
            NormalizedIntegrationError(
                code="INTEGRATION_PROVIDER_ERROR",
                category="integration",
                provider_key=health.provider,
                retryable=True,
                user_facing_message="Integration provider health check failed.",
                operator_message=(
                    f"Provider {health.provider} is unhealthy: "
                    f"{health.details or 'unknown reason'}"
                ),
            )
        )
    return health
