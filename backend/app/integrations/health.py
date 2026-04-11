"""Provider health models and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.errors import ProviderHealthError


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    healthy: bool
    details: str = ""


def ensure_healthy(health: ProviderHealth) -> ProviderHealth:
    if not health.healthy:
        raise ProviderHealthError(
            f"Provider {health.provider} is unhealthy: {health.details or 'unknown reason'}"
        )
    return health
