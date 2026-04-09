"""Integration domain and capability models."""

from __future__ import annotations

from enum import Enum
from typing import TypeAlias


class IntegrationDomain(str, Enum):
    """High-level integration domains used by route handlers and services."""

    TELEMATICS = "telematics"
    DASHCAM = "dashcam"
    MESSAGING = "messaging"
    STORAGE = "storage"
    FLEET_DIRECTORY = "fleet_directory"


class ProviderCapability(str, Enum):
    """Capability keys resolved through the provider registry."""

    TELEMATICS = "telematics"
    DASHCAM = "dashcam"
    MESSAGING = "messaging"
    STORAGE = "storage"
    FLEET_DIRECTORY = "fleet_directory"


ProviderName: TypeAlias = str
