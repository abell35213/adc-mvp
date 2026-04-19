"""Organization commercial plan + entitlement routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.emitter import emit_standard_audit_event
from app.commercial.enforcement import (
    INTERNAL_OVERRIDE_ROLES,
    is_internal_override_actor,
    resolve_org_access_snapshot,
)
from app.core.deps import get_current_user, require_user_role
from app.db.models import User
from app.db.repo.org_content import (
    get_org_plan_entitlement,
    upsert_org_plan_entitlement,
)
from app.db.session import get_db
from app.security.authn import build_user_auth_context

router = APIRouter(prefix="/org", tags=["org-entitlements"])

_org_entitlement_mutator = require_user_role(
    "system_admin",
    "org_admin",
    "support_admin",
    "support_agent",
)


class OrgPlanResponse(BaseModel):
    org_id: uuid.UUID
    plan_code: str
    billing_status: str
    core_incident_protocol: bool
    effective_from_utc: str | None
    effective_to_utc: str | None


class EntitlementItem(BaseModel):
    key: str
    enabled: bool


class ModuleItem(BaseModel):
    key: str
    enabled: bool = True


class OrgEntitlementsResponse(BaseModel):
    org_id: uuid.UUID
    plan_code: str
    billing_status: str
    modules: list[ModuleItem]
    entitlements: list[EntitlementItem]
    feature_flags: dict[str, bool]
    internal_override_eligible_roles: list[str]


class OrgModulesResponse(BaseModel):
    org_id: uuid.UUID
    plan_code: str
    modules: list[ModuleItem]


class EntitlementInternalOverride(BaseModel):
    reason: str = Field(min_length=3, max_length=256)
    ticket_id: str | None = Field(default=None, max_length=128)
    actor_path: str = Field(default="support")


class OrgEntitlementPatchRequest(BaseModel):
    plan_code: str | None = None
    billing_status: str | None = None
    core_incident_protocol: bool | None = None
    entitlements: dict[str, bool] | None = None
    internal_override: EntitlementInternalOverride | None = None


def _resolve_org_context(db: Session, user: User) -> tuple[uuid.UUID, Any]:
    context = build_user_auth_context(db, user)
    return context.org_ids[0], context


def _serialize_plan(org_id: uuid.UUID, row) -> OrgPlanResponse:
    return OrgPlanResponse(
        org_id=org_id,
        plan_code=row.plan_code,
        billing_status=row.billing_status,
        core_incident_protocol=bool(row.core_incident_protocol),
        effective_from_utc=row.effective_from_utc.isoformat()
        if row.effective_from_utc
        else None,
        effective_to_utc=row.effective_to_utc.isoformat()
        if row.effective_to_utc
        else None,
    )


def _serialize_entitlements(org_id: uuid.UUID, db: Session) -> OrgEntitlementsResponse:
    snapshot = resolve_org_access_snapshot(db, org_id=org_id)
    row = get_org_plan_entitlement(db, org_id)
    billing_status = row.billing_status if row is not None else "active"

    entitlements = [
        EntitlementItem(key=key, enabled=enabled)
        for key, enabled in snapshot["entitlements"].items()
    ]
    modules = [ModuleItem(key=key, enabled=True) for key in snapshot["modules"]]

    return OrgEntitlementsResponse(
        org_id=org_id,
        plan_code=str(snapshot["plan_code"]),
        billing_status=billing_status,
        modules=modules,
        entitlements=entitlements,
        feature_flags=dict(snapshot["entitlements"]),
        internal_override_eligible_roles=sorted(INTERNAL_OVERRIDE_ROLES),
    )


@router.get("/plan", response_model=OrgPlanResponse)
def get_org_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _resolve_org_context(db, current_user)
    row = get_org_plan_entitlement(db, org_id)
    if row is None:
        row = upsert_org_plan_entitlement(db, org_id, plan_code="starter")
    return _serialize_plan(org_id, row)


@router.get("/entitlements", response_model=OrgEntitlementsResponse)
def get_org_entitlements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _resolve_org_context(db, current_user)
    if get_org_plan_entitlement(db, org_id) is None:
        upsert_org_plan_entitlement(db, org_id, plan_code="starter")
    return _serialize_entitlements(org_id, db)


@router.patch("/entitlements", response_model=OrgEntitlementsResponse)
def patch_org_entitlements(
    payload: OrgEntitlementPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_org_entitlement_mutator),
):
    org_id, _ = _resolve_org_context(db, current_user)
    existing = get_org_plan_entitlement(db, org_id)
    if existing is None:
        existing = upsert_org_plan_entitlement(db, org_id, plan_code="starter")

    override_metadata: dict[str, Any] = {}
    if payload.internal_override is not None:
        if not is_internal_override_actor(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Internal override requires internal role",
            )
        override_metadata = {
            "internal_override": {
                "applied": True,
                "reason": payload.internal_override.reason,
                "ticket_id": payload.internal_override.ticket_id,
                "actor_path": payload.internal_override.actor_path,
                "actor_role": (current_user.role or "").strip().lower(),
            }
        }

    previous_plan_code = existing.plan_code

    updated = upsert_org_plan_entitlement(
        db,
        org_id,
        plan_code=payload.plan_code or existing.plan_code,
        billing_status=payload.billing_status or existing.billing_status,
        core_incident_protocol=(
            payload.core_incident_protocol
            if payload.core_incident_protocol is not None
            else bool(existing.core_incident_protocol)
        ),
        entitlements_json=(
            payload.entitlements
            if payload.entitlements is not None
            else dict(existing.entitlements_json or {})
        ),
    )

    if payload.plan_code is not None and payload.plan_code != previous_plan_code:
        emit_standard_audit_event(
            db,
            org_id=org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="org.plan.update",
            event_type="org_plan_changed",
            entity_type="org_plan",
            entity_id=str(org_id),
            outcome="success",
            metadata={
                "before": {"plan_code": previous_plan_code},
                "after": {"plan_code": updated.plan_code},
                **override_metadata,
            },
        )

    if payload.entitlements is not None:
        emit_standard_audit_event(
            db,
            org_id=org_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="org.entitlements.update",
            event_type="feature_entitlement_updated",
            entity_type="org_entitlements",
            entity_id=str(org_id),
            outcome="success",
            metadata={
                "feature_flags": dict(updated.entitlements_json or {}),
                **override_metadata,
            },
        )

    return _serialize_entitlements(org_id, db)


@router.get("/modules", response_model=OrgModulesResponse)
def get_org_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id, _ = _resolve_org_context(db, current_user)
    if get_org_plan_entitlement(db, org_id) is None:
        upsert_org_plan_entitlement(db, org_id, plan_code="starter")
    snapshot = resolve_org_access_snapshot(db, org_id=org_id)
    return OrgModulesResponse(
        org_id=org_id,
        plan_code=str(snapshot["plan_code"]),
        modules=[ModuleItem(key=key, enabled=True) for key in snapshot["modules"]],
    )
