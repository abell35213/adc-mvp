"""Commercial plan primitives and plan resolution helpers."""

from __future__ import annotations

from enum import Enum


class ProductPlan(str, Enum):
    """Canonical product plans in ascending commercial capability order."""

    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


_PLAN_ORDER: tuple[ProductPlan, ...] = (
    ProductPlan.STARTER,
    ProductPlan.GROWTH,
    ProductPlan.ENTERPRISE,
)


def resolve_plan(
    plan: ProductPlan | str | None,
    *,
    default: ProductPlan = ProductPlan.STARTER,
) -> ProductPlan:
    """Resolve user or database plan values to a canonical ``ProductPlan``."""
    if isinstance(plan, ProductPlan):
        return plan
    if isinstance(plan, str):
        normalized = plan.strip().lower()
        if normalized:
            try:
                return ProductPlan(normalized)
            except ValueError:
                pass
    return default


def plan_rank(plan: ProductPlan | str | None) -> int:
    """Return an integer rank for capability comparisons."""
    resolved = resolve_plan(plan)
    return _PLAN_ORDER.index(resolved)
