"""Tests for role-to-capability mapping."""

from app.security.permissions import Capability, can_mutate_demo_tenant, get_user_capabilities


def test_claims_user_capabilities_include_incident_write_and_export_write():
    capabilities = get_user_capabilities("claims_user")
    assert Capability.INCIDENT_READ in capabilities
    assert Capability.INCIDENT_WRITE in capabilities
    assert Capability.EXPORT_WRITE in capabilities
    assert Capability.INCIDENT_CLOSE not in capabilities


def test_read_only_capabilities_are_read_only():
    capabilities = get_user_capabilities("read_only")
    assert Capability.INCIDENT_READ in capabilities
    assert Capability.EXPORT_READ in capabilities
    assert Capability.READINESS_VIEW in capabilities
    assert Capability.USER_MANAGEMENT_READ in capabilities
    assert Capability.INCIDENT_WRITE not in capabilities
    assert Capability.EXPORT_WRITE not in capabilities
    assert Capability.IMPORTS_WRITE not in capabilities


def test_support_admin_includes_phase6_management_capabilities():
    capabilities = get_user_capabilities("support_admin")
    assert Capability.ORG_SETTINGS_WRITE in capabilities
    assert Capability.USER_MANAGEMENT_WRITE in capabilities
    assert Capability.IMPORTS_WRITE in capabilities
    assert Capability.VEHICLE_QR_WRITE in capabilities
    assert Capability.INTEGRATIONS_WRITE in capabilities
    assert Capability.ONBOARDING_WRITE in capabilities
    assert Capability.TEST_RUNS_WRITE in capabilities


def test_only_internal_roles_can_mutate_demo_tenant():
    assert can_mutate_demo_tenant("system_admin") is True
    assert can_mutate_demo_tenant("support_admin") is True
    assert can_mutate_demo_tenant("org_admin") is False
