"""Commercial module catalog and plan-to-module projection."""

from __future__ import annotations

from enum import Enum

from app.commercial.plans import ProductPlan, resolve_plan


class ProductModule(str, Enum):
    ONBOARDING = "onboarding"
    CASE_OPS = "case_ops"
    REPORTING = "reporting"
    EXPANSION = "expansion"
    TRUST = "trust"
    DEMO = "demo"
    DOCS = "docs"


_PLAN_MODULES: dict[ProductPlan, tuple[ProductModule, ...]] = {
    ProductPlan.STARTER: (
        ProductModule.ONBOARDING,
        ProductModule.CASE_OPS,
        ProductModule.DOCS,
    ),
    ProductPlan.GROWTH: (
        ProductModule.ONBOARDING,
        ProductModule.CASE_OPS,
        ProductModule.REPORTING,
        ProductModule.DOCS,
        ProductModule.DEMO,
    ),
    ProductPlan.ENTERPRISE: (
        ProductModule.ONBOARDING,
        ProductModule.CASE_OPS,
        ProductModule.REPORTING,
        ProductModule.EXPANSION,
        ProductModule.TRUST,
        ProductModule.DOCS,
        ProductModule.DEMO,
    ),
}


def list_modules_by_plan(plan: ProductPlan | str | None) -> list[ProductModule]:
    """List enabled modules for the given plan."""
    return list(_PLAN_MODULES[resolve_plan(plan)])
