"""Tests for role-to-capability mapping."""

from app.security.permissions import Capability, get_user_capabilities


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
    assert Capability.INCIDENT_WRITE not in capabilities
    assert Capability.EXPORT_WRITE not in capabilities
