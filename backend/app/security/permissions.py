"""Canonical auth roles and capability mapping."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    SYSTEM_ADMIN = "system_admin"
    ORG_ADMIN = "org_admin"
    SAFETY_MANAGER = "safety_manager"
    CLAIMS_USER = "claims_user"
    READ_ONLY = "read_only"
    SUPPORT_ADMIN = "support_admin"
    SUPPORT_AGENT = "support_agent"


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
    ORG_SETTINGS_READ = "org_settings:read"
    ORG_SETTINGS_WRITE = "org_settings:write"
    USER_MANAGEMENT_READ = "user_management:read"
    USER_MANAGEMENT_WRITE = "user_management:write"
    IMPORTS_READ = "imports:read"
    IMPORTS_WRITE = "imports:write"
    INTEGRATIONS_READ = "integrations:read"
    INTEGRATIONS_WRITE = "integrations:write"
    ONBOARDING_READ = "onboarding:read"
    ONBOARDING_WRITE = "onboarding:write"
    TEST_RUNS_READ = "test_runs:read"
    TEST_RUNS_WRITE = "test_runs:write"
    READINESS_VIEW = "readiness:view"
    DEMO_MANAGE = "demo:manage"
    ENTITLEMENTS_MANAGE = "entitlements:manage"
    TRUST_DOCS_PUBLISH = "trust_docs:publish"
    DEPLOYMENT_SCOPE_MANAGE = "deployment_scope:manage"
    REPORTING_BASIC_READ = "reporting:basic_read"
    REPORTING_PREMIUM_READ = "reporting:premium_read"


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
    "support_admin": Role.SUPPORT_ADMIN,
    "support admin": Role.SUPPORT_ADMIN,
    "support-admin": Role.SUPPORT_ADMIN,
    "supportadministrator": Role.SUPPORT_ADMIN,
    "support-agent": Role.SUPPORT_AGENT,
    "support_agent": Role.SUPPORT_AGENT,
    "support agent": Role.SUPPORT_AGENT,
    "supportagent": Role.SUPPORT_AGENT,
    "support": Role.SUPPORT_AGENT,
}

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.SYSTEM_ADMIN: frozenset(Capability),
    Role.ORG_ADMIN: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.INCIDENT_CLOSE,
            Capability.INCIDENT_REOPEN,
            Capability.INCIDENT_ESCALATE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
            Capability.DRIVER_PROTOCOL_READ,
            Capability.DRIVER_PROTOCOL_WRITE,
            Capability.VEHICLE_QR_READ,
            Capability.VEHICLE_QR_WRITE,
            Capability.ORG_SETTINGS_READ,
            Capability.ORG_SETTINGS_WRITE,
            Capability.USER_MANAGEMENT_READ,
            Capability.USER_MANAGEMENT_WRITE,
            Capability.IMPORTS_READ,
            Capability.IMPORTS_WRITE,
            Capability.INTEGRATIONS_READ,
            Capability.INTEGRATIONS_WRITE,
            Capability.ONBOARDING_READ,
            Capability.ONBOARDING_WRITE,
            Capability.TEST_RUNS_READ,
            Capability.TEST_RUNS_WRITE,
            Capability.READINESS_VIEW,
            Capability.ENTITLEMENTS_MANAGE,
            Capability.DEPLOYMENT_SCOPE_MANAGE,
            Capability.REPORTING_BASIC_READ,
            Capability.REPORTING_PREMIUM_READ,
        }
    ),
    Role.SAFETY_MANAGER: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
            Capability.IMPORTS_READ,
            Capability.IMPORTS_WRITE,
            Capability.VEHICLE_QR_READ,
            Capability.VEHICLE_QR_WRITE,
            Capability.ORG_SETTINGS_READ,
            Capability.ORG_SETTINGS_WRITE,
            Capability.INTEGRATIONS_READ,
            Capability.ONBOARDING_READ,
            Capability.ONBOARDING_WRITE,
            Capability.TEST_RUNS_READ,
            Capability.TEST_RUNS_WRITE,
            Capability.READINESS_VIEW,
            Capability.DEPLOYMENT_SCOPE_MANAGE,
            Capability.REPORTING_BASIC_READ,
            Capability.REPORTING_PREMIUM_READ,
        }
    ),
    Role.CLAIMS_USER: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.INCIDENT_WRITE,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
            Capability.READINESS_VIEW,
            Capability.REPORTING_BASIC_READ,
            Capability.REPORTING_PREMIUM_READ,
        }
    ),
    Role.READ_ONLY: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.EXPORT_READ,
            Capability.IMPORTS_READ,
            Capability.VEHICLE_QR_READ,
            Capability.INTEGRATIONS_READ,
            Capability.ONBOARDING_READ,
            Capability.TEST_RUNS_READ,
            Capability.ORG_SETTINGS_READ,
            Capability.USER_MANAGEMENT_READ,
            Capability.READINESS_VIEW,
            Capability.REPORTING_BASIC_READ,
        }
    ),
    Role.SUPPORT_ADMIN: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.EXPORT_READ,
            Capability.EXPORT_WRITE,
            Capability.ORG_SETTINGS_READ,
            Capability.ORG_SETTINGS_WRITE,
            Capability.USER_MANAGEMENT_READ,
            Capability.USER_MANAGEMENT_WRITE,
            Capability.IMPORTS_READ,
            Capability.IMPORTS_WRITE,
            Capability.VEHICLE_QR_READ,
            Capability.VEHICLE_QR_WRITE,
            Capability.INTEGRATIONS_READ,
            Capability.INTEGRATIONS_WRITE,
            Capability.ONBOARDING_READ,
            Capability.ONBOARDING_WRITE,
            Capability.TEST_RUNS_READ,
            Capability.TEST_RUNS_WRITE,
            Capability.READINESS_VIEW,
            Capability.DEMO_MANAGE,
            Capability.ENTITLEMENTS_MANAGE,
            Capability.TRUST_DOCS_PUBLISH,
            Capability.DEPLOYMENT_SCOPE_MANAGE,
            Capability.REPORTING_BASIC_READ,
            Capability.REPORTING_PREMIUM_READ,
        }
    ),
    Role.SUPPORT_AGENT: frozenset(
        {
            Capability.INCIDENT_READ,
            Capability.EXPORT_READ,
            Capability.ORG_SETTINGS_READ,
            Capability.USER_MANAGEMENT_READ,
            Capability.IMPORTS_READ,
            Capability.VEHICLE_QR_READ,
            Capability.INTEGRATIONS_READ,
            Capability.ONBOARDING_READ,
            Capability.TEST_RUNS_READ,
            Capability.READINESS_VIEW,
            Capability.ENTITLEMENTS_MANAGE,
            Capability.TRUST_DOCS_PUBLISH,
            Capability.REPORTING_BASIC_READ,
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


def can_mutate_demo_tenant(raw_role: str | None) -> bool:
    """Return whether the provided role can mutate demo tenant state."""
    return has_capability(raw_role, Capability.DEMO_MANAGE)
