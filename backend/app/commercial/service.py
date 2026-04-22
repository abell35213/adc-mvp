"""Commercial service facade with dependency-injected data access."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Protocol

from app.commercial.entitlements import (
    EntitlementMap,
    is_feature_enabled,
    resolve_entitlements,
)
from app.commercial.modules import ProductModule, list_modules_by_plan
from app.commercial.plans import ProductPlan, resolve_plan


class PlanRepository(Protocol):
    def get_plan_for_org(self, org_id: uuid.UUID) -> ProductPlan | str | None: ...


class EntitlementRepository(Protocol):
    def get_overrides_for_org(self, org_id: uuid.UUID) -> Mapping[str, bool]: ...


def resolve_org_plan(*, org_id: uuid.UUID, plan_repo: PlanRepository) -> ProductPlan:
    """Resolve the canonical product plan for an organization."""
    return resolve_plan(plan_repo.get_plan_for_org(org_id))


def resolve_org_entitlements(
    *,
    org_id: uuid.UUID,
    plan_repo: PlanRepository,
    entitlement_repo: EntitlementRepository | None = None,
    plan_overrides: Mapping[str, bool] | None = None,
) -> EntitlementMap:
    """Resolve entitlements by loading org data via repository interfaces."""
    plan = resolve_org_plan(org_id=org_id, plan_repo=plan_repo)
    org_overrides = (
        entitlement_repo.get_overrides_for_org(org_id)
        if entitlement_repo is not None
        else None
    )
    return resolve_entitlements(
        plan=plan,
        plan_overrides=plan_overrides,
        org_overrides=org_overrides,
    )


def list_org_modules(*, org_id: uuid.UUID, plan_repo: PlanRepository) -> list[ProductModule]:
    """Return modules enabled for the organization plan."""
    return list_modules_by_plan(resolve_org_plan(org_id=org_id, plan_repo=plan_repo))


def is_feature_enabled_for_org(
    *,
    org_id: uuid.UUID,
    feature_key: str,
    actor_role: str,
    plan_repo: PlanRepository,
    entitlement_repo: EntitlementRepository | None = None,
    overrides: Mapping[str, bool] | None = None,
    role_allowlist: Mapping[str, set[str]] | None = None,
) -> bool:
    """Dependency-injected feature gate check.

    If ``overrides`` are provided at call time, they are merged over repository overrides.
    """
    plan = resolve_org_plan(org_id=org_id, plan_repo=plan_repo)
    repo_overrides = (
        entitlement_repo.get_overrides_for_org(org_id)
        if entitlement_repo is not None
        else None
    )
    merged_overrides: dict[str, bool] = {}
    if repo_overrides is not None:
        merged_overrides.update({str(k): bool(v) for k, v in repo_overrides.items()})
    if overrides is not None:
        merged_overrides.update({str(k): bool(v) for k, v in overrides.items()})
    return is_feature_enabled(
        org_id=org_id,
        feature_key=feature_key,
        actor_role=actor_role,
        overrides=merged_overrides,
        plan=plan,
        role_allowlist=role_allowlist,
    )
