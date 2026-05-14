"""Centralized authorization policy checks."""

from __future__ import annotations

import uuid
from typing import cast

from fastapi import HTTPException, status

from app.db.models import Export, Incident
from app.security.authn import DriverAuthContext, UserAuthContext
from app.security.permissions import Capability, has_capability


FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _belongs_to_member_org(resource_org_id: uuid.UUID | None, member_org_ids: tuple[uuid.UUID, ...]) -> bool:
    return resource_org_id is not None and resource_org_id in member_org_ids


def can_create_incident(context: UserAuthContext) -> bool:
    return has_capability(cast(str | None, context.user.role), Capability.INCIDENT_WRITE) and bool(context.org_ids)


def can_view_incident(context: UserAuthContext, incident: Incident | None) -> bool:
    return (
        incident is not None
        and has_capability(cast(str | None, context.user.role), Capability.INCIDENT_READ)
        and _belongs_to_member_org(cast(uuid.UUID | None, incident.org_id), context.org_ids)
    )


def can_modify_incident(context: UserAuthContext, incident: Incident | None) -> bool:
    return (
        incident is not None
        and has_capability(cast(str | None, context.user.role), Capability.INCIDENT_WRITE)
        and _belongs_to_member_org(cast(uuid.UUID | None, incident.org_id), context.org_ids)
    )


def can_request_export(context: UserAuthContext, incident: Incident | None) -> bool:
    return (
        incident is not None
        and has_capability(cast(str | None, context.user.role), Capability.EXPORT_WRITE)
        and _belongs_to_member_org(cast(uuid.UUID | None, incident.org_id), context.org_ids)
    )


def can_download_export(context: UserAuthContext, export: Export | None, *, export_org_id: uuid.UUID | None) -> bool:
    return (
        export is not None
        and has_capability(cast(str | None, context.user.role), Capability.EXPORT_READ)
        and _belongs_to_member_org(export_org_id, context.org_ids)
    )


def can_access_admin_org(context: UserAuthContext, org_id: uuid.UUID | None, capability: Capability) -> bool:
    return org_id is not None and has_capability(cast(str | None, context.user.role), capability) and org_id in context.org_ids


def can_access_driver_incident(context: DriverAuthContext, incident: Incident | None) -> bool:
    return (
        incident is not None
        and bool(cast(uuid.UUID | None, incident.org_id) == context.org_id)
        and bool(cast(str | None, incident.adc_driver_id) == str(context.driver.driver_id))
    )


def require_policy(allowed: bool) -> None:
    if not allowed:
        raise FORBIDDEN
