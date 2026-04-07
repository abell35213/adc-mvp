"""Canonical auth roles and capability mapping."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SAFETY_MANAGER = "safety_manager"


class Capability(str, Enum):
    INCIDENT_READ = "incident:read"
    INCIDENT_WRITE = "incident:write"
    EXPORT_READ = "export:read"
    EXPORT_WRITE = "export:write"
    DRIVER_PROTOCOL_READ = "driver_protocol:read"
    DRIVER_PROTOCOL_WRITE = "driver_protocol:write"
    VEHICLE_QR_READ = "vehicle_qr:read"
    VEHICLE_QR_WRITE = "vehicle_qr:write"


CANONICAL_ROLES: tuple[str, ...] = tuple(role.value for role in Role)
ALL_RECOMMENDED_CAPABILITIES: tuple[str, ...] = tuple(
    capability.value for capability in Capability
)

_ROLE_ALIASES: dict[str, Role] = {
    "admin": Role.ADMIN,
    "administrator": Role.ADMIN,
    "super_admin": Role.ADMIN,
    "superadmin": Role.ADMIN,
    "safety_manager": Role.SAFETY_MANAGER,
    "safety manager": Role.SAFETY_MANAGER,
    "safety-manager": Role.SAFETY_MANAGER,
    "manager": Role.SAFETY_MANAGER,
}

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ADMIN: frozenset(Capability),
    Role.SAFETY_MANAGER: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
        }
    ),
}


def normalize_role(raw_role: str | None) -> Role:
    candidate = (raw_role or "").strip().lower()
    if candidate in _ROLE_ALIASES:
        return _ROLE_ALIASES[candidate]
    return Role.SAFETY_MANAGER


def get_user_capabilities(raw_role: str | None) -> frozenset[Capability]:
    return ROLE_CAPABILITIES[normalize_role(raw_role)]
