"""Entitlement enforcement helpers for API route-level feature gates."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.audit.emitter import emit_standard_audit_event
from app.commercial.service import (
    is_feature_enabled_for_org,
    list_org_modules,
    resolve_org_entitlements,
    resolve_org_plan,
)
from app.db.repo.org_content import get_org_plan_entitlement

INTERNAL_OVERRIDE_ROLES = {"system_admin", "support_admin", "support_agent"}


class _OrgPlanRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_plan_for_org(self, org_id: uuid.UUID) -> str | None:
        row = get_org_plan_entitlement(self._db, org_id)
        return str(row.plan_code) if row is not None and row.plan_code is not None else None


class _OrgEntitlementRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_overrides_for_org(self, org_id: uuid.UUID) -> dict[str, bool]:
        row = get_org_plan_entitlement(self._db, org_id)
        data = dict(row.entitlements_json or {}) if row is not None else {}
        return {str(key): bool(value) for key, value in data.items()}


@dataclass(frozen=True)
class EntitlementDecision:
    enabled: bool
    via_internal_override: bool


def _normalize_role(role: str | None) -> str:
    return (role or "").strip().lower()


def is_internal_override_actor(role: str | None) -> bool:
    return _normalize_role(role) in INTERNAL_OVERRIDE_ROLES


def entitlement_decision(
    db: Session,
    *,
    org_id: uuid.UUID,
    feature_key: str,
    actor_role: str,
    allow_internal_override: bool = False,
) -> EntitlementDecision:
    plan_repo = _OrgPlanRepository(db)
    ent_repo = _OrgEntitlementRepository(db)
    enabled = is_feature_enabled_for_org(
        org_id=org_id,
        feature_key=feature_key,
        actor_role=actor_role,
        plan_repo=plan_repo,
        entitlement_repo=ent_repo,
    )
    if enabled:
        return EntitlementDecision(enabled=True, via_internal_override=False)

    via_internal_override = allow_internal_override and is_internal_override_actor(
        actor_role
    )
    return EntitlementDecision(
        enabled=via_internal_override, via_internal_override=via_internal_override
    )


def require_feature_enabled(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: str,
    actor_role: str,
    feature_key: str,
    action: str,
    allow_internal_override: bool = False,
) -> EntitlementDecision:
    decision = entitlement_decision(
        db,
        org_id=org_id,
        feature_key=feature_key,
        actor_role=actor_role,
        allow_internal_override=allow_internal_override,
    )
    if not decision.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature unavailable",
        )

    if decision.via_internal_override:
        emit_standard_audit_event(
            db,
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            action=action,
            event_type="feature_entitlement_override_used",
            entity_type="feature",
            entity_id=feature_key,
            outcome="success",
            metadata={
                "internal_override": {
                    "applied": True,
                    "actor_role": _normalize_role(actor_role),
                    "reason": "demo_support_override_path",
                }
            },
        )

    return decision


def resolve_org_access_snapshot(db: Session, *, org_id: uuid.UUID) -> dict[str, object]:
    plan_repo = _OrgPlanRepository(db)
    ent_repo = _OrgEntitlementRepository(db)
    plan = resolve_org_plan(org_id=org_id, plan_repo=plan_repo)
    modules = [
        module.value for module in list_org_modules(org_id=org_id, plan_repo=plan_repo)
    ]
    entitlements = resolve_org_entitlements(
        org_id=org_id,
        plan_repo=plan_repo,
        entitlement_repo=ent_repo,
    )
    return {
        "plan_code": plan.value,
        "modules": modules,
        "entitlements": {str(k): bool(v) for k, v in sorted(entitlements.items())},
    }
