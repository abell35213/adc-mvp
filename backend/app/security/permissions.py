"""Canonical auth roles and capability mapping."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    ORG_ADMIN = "org_admin"
    SAFETY_MANAGER = "safety_manager"
    CLAIMS_USER = "claims_user"
    READ_ONLY = "read_only"


class Capability(str, Enum):
    INCIDENT_READ = "incident:read"
    INCIDENT_WRITE = "incident:write"
    INCIDENT_CLOSE = "incident:close"
    INCIDENT_REOPEN = "incident:reopen"
    INCIDENT_ESCALATE = "incident:escalate"
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
    "system_admin": Role.SYSTEM_ADMIN,
    "system admin": Role.SYSTEM_ADMIN,
    "org_admin": Role.ORG_ADMIN,
    "org admin": Role.ORG_ADMIN,
    "admin": Role.ORG_ADMIN,
    "administrator": Role.ORG_ADMIN,
    "super_admin": Role.SYSTEM_ADMIN,
    "superadmin": Role.SYSTEM_ADMIN,
    "safety_manager": Role.SAFETY_MANAGER,
    "safety manager": Role.SAFETY_MANAGER,
    "safety-manager": Role.SAFETY_MANAGER,
    "manager": Role.SAFETY_MANAGER,
    "claims_user": Role.CLAIMS_USER,
    "claims user": Role.CLAIMS_USER,
    "claims-user": Role.CLAIMS_USER,
    "read_only": Role.READ_ONLY,
    "read only": Role.READ_ONLY,
    "readonly": Role.READ_ONLY,
}

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.SYSTEM_ADMIN: frozenset(Capability),
    Role.ORG_ADMIN: frozenset(Capability),
    Role.SAFETY_MANAGER: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
        }
    ),
    Role.CLAIMS_USER: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
        }
    ),
    Role.READ_ONLY: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.EXPORT_READ,
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


def has_capability(raw_role: str | None, capability: Capability | str) -> bool:
    resolved = (
        capability if isinstance(capability, Capability) else Capability(capability)
    )
    return resolved in get_user_capabilities(raw_role)
