import uuid

from app.commercial.entitlements import (
    merge_entitlements,
    resolve_entitlements,
)
from app.commercial.modules import ProductModule, list_modules_by_plan
from app.commercial.plans import ProductPlan, resolve_plan
from app.commercial.service import (
    is_feature_enabled_for_org,
    list_org_modules,
    resolve_org_entitlements,
)


class _StaticPlanRepo:
    def __init__(self, plan: str):
        self._plan = plan

    def get_plan_for_org(self, org_id: uuid.UUID) -> str:
        _ = org_id
        return self._plan


class _StaticEntitlementRepo:
    def __init__(self, overrides: dict[str, bool]):
        self._overrides = overrides

    def get_overrides_for_org(self, org_id: uuid.UUID) -> dict[str, bool]:
        _ = org_id
        return self._overrides


def test_resolve_plan_normalizes_unknown_to_default():
    assert resolve_plan("enterprise") == ProductPlan.ENTERPRISE
    assert resolve_plan("unknown-plan") == ProductPlan.STARTER


def test_list_modules_by_plan_returns_expected_catalog():
    starter_modules = list_modules_by_plan(ProductPlan.STARTER)
    enterprise_modules = list_modules_by_plan(ProductPlan.ENTERPRISE)

    assert ProductModule.REPORTING not in starter_modules
    assert ProductModule.TRUST in enterprise_modules


def test_merge_and_resolve_entitlements_apply_overrides_last_write_wins():
    merged = merge_entitlements(
        {"reporting.dashboard": True, "demo.workspace": True},
        {"demo.workspace": False},
    )
    assert merged["demo.workspace"] is False

    resolved = resolve_entitlements(
        plan=ProductPlan.STARTER,
        org_overrides={"reporting.dashboard": True},
    )
    assert resolved["reporting.dashboard"] is True


def test_dependency_injected_service_interfaces():
    org_id = uuid.uuid4()
    plan_repo = _StaticPlanRepo("growth")
    ent_repo = _StaticEntitlementRepo({"reporting.dashboard": True})

    modules = list_org_modules(org_id=org_id, plan_repo=plan_repo)
    entitlements = resolve_org_entitlements(
        org_id=org_id,
        plan_repo=plan_repo,
        entitlement_repo=ent_repo,
    )

    assert ProductModule.REPORTING in modules
    assert entitlements["reporting.dashboard"] is True


def test_is_feature_enabled_for_org_with_role_allowlist_and_overrides():
    org_id = uuid.uuid4()
    plan_repo = _StaticPlanRepo("enterprise")
    ent_repo = _StaticEntitlementRepo({"trust.sso": True})

    allowed = is_feature_enabled_for_org(
        org_id=org_id,
        feature_key="trust.sso",
        actor_role="org_admin",
        plan_repo=plan_repo,
        entitlement_repo=ent_repo,
        role_allowlist={"trust.sso": {"org_admin"}},
    )
    blocked = is_feature_enabled_for_org(
        org_id=org_id,
        feature_key="trust.sso",
        actor_role="viewer",
        plan_repo=plan_repo,
        entitlement_repo=ent_repo,
        role_allowlist={"trust.sso": {"org_admin"}},
        overrides={"trust.sso": True},
    )

    assert allowed is True
    assert blocked is False
