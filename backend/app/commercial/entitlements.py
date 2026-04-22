"""Entitlement merge and feature-gate checks."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.commercial.demo import DEMO_FEATURES
from app.commercial.docs import DOCS_FEATURES
from app.commercial.expansion import EXPANSION_FEATURES
from app.commercial.modules import list_modules_by_plan
from app.commercial.plans import ProductPlan, resolve_plan
from app.commercial.reporting import REPORTING_FEATURES
from app.commercial.trust import TRUST_FEATURES

EntitlementMap = dict[str, bool]

_MODULE_FEATURES: dict[str, tuple[str, ...]] = {
    "onboarding": ("onboarding.readiness", "onboarding.imports"),
    "case_ops": ("case_ops.workspace", "case_ops.transitions"),
    "reporting": REPORTING_FEATURES,
    "expansion": EXPANSION_FEATURES,
    "trust": TRUST_FEATURES,
    "demo": DEMO_FEATURES,
    "docs": DOCS_FEATURES,
}


def base_entitlements_for_plan(plan: ProductPlan | str | None) -> EntitlementMap:
    """Build base feature entitlements from enabled modules for a plan."""
    entitlements: EntitlementMap = {}
    for module in list_modules_by_plan(plan):
        for feature_key in _MODULE_FEATURES.get(module.value, ()):  # defensive
            entitlements[feature_key] = True
    return entitlements


def merge_entitlements(
    base: Mapping[str, bool],
    *overlays: Mapping[str, bool] | None,
) -> EntitlementMap:
    """Merge base entitlements with optional overlays (last-write-wins)."""
    merged: EntitlementMap = dict(base)
    for overlay in overlays:
        if overlay is None:
            continue
        for key, value in overlay.items():
            merged[str(key)] = bool(value)
    return merged


def resolve_entitlements(
    *,
    plan: ProductPlan | str | None,
    plan_overrides: Mapping[str, bool] | None = None,
    org_overrides: Mapping[str, bool] | None = None,
) -> EntitlementMap:
    """Resolve final entitlement map from plan defaults + overrides."""
    base = base_entitlements_for_plan(resolve_plan(plan))
    return merge_entitlements(base, plan_overrides, org_overrides)


def is_feature_enabled(
    org_id: uuid.UUID,
    feature_key: str,
    actor_role: str,
    overrides: Mapping[str, bool] | None,
    *,
    plan: ProductPlan | str | None,
    entitlements: Mapping[str, bool] | None = None,
    role_allowlist: Mapping[str, set[str]] | None = None,
) -> bool:
    """Evaluate whether a feature is enabled for an org/user context.

    ``org_id`` is accepted for telemetry/event parity with calling layers.
    """
    _ = org_id
    effective = (
        dict(entitlements)
        if entitlements is not None
        else resolve_entitlements(plan=plan, org_overrides=overrides)
    )
    enabled = bool(effective.get(feature_key, False))
    if not enabled:
        return False
    if role_allowlist is None:
        return True
    allowed_roles = role_allowlist.get(feature_key)
    if not allowed_roles:
        return True
    return actor_role in allowed_roles
