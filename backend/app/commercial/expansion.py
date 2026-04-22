"""Deployment scope and expansion readiness service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Driver,
    OrgExportValidationRun,
    OrgTestIncidentRun,
    User,
    UserOrg,
)
from app.db.repo.org_content import (
    create_deployment_scope_snapshot,
    get_latest_deployment_scope_snapshot,
    upsert_expansion_readiness_snapshot,
)
from app.onboarding.service import collect_onboarding_signals

from typing import Literal

ExpansionReadiness = Literal[
    "not_started",
    "planning",
    "pilot_ready",
    "scale_ready",
    "blocked",
]
DeploymentScopeKey = Literal["pilot", "partial_rollout", "full_rollout"]

EXPANSION_READINESS_STATES: tuple[ExpansionReadiness, ...] = (
    "not_started",
    "planning",
    "pilot_ready",
    "scale_ready",
    "blocked",
)
DEPLOYMENT_SCOPE_KEYS: tuple[DeploymentScopeKey, ...] = (
    "pilot",
    "partial_rollout",
    "full_rollout",
)

EXPANSION_FEATURES: tuple[str, ...] = (
    "expansion.scorecard",
    "expansion.rollout",
)

DEFAULT_TARGETS_BY_SCOPE: dict[DeploymentScopeKey, dict[str, int]] = {
    "pilot": {
        "vehicles": 5,
        "drivers": 10,
        "admins": 1,
        "test_incidents": 1,
        "exports": 1,
    },
    "partial_rollout": {
        "vehicles": 25,
        "drivers": 50,
        "admins": 2,
        "test_incidents": 3,
        "exports": 2,
    },
    "full_rollout": {
        "vehicles": 100,
        "drivers": 200,
        "admins": 3,
        "test_incidents": 5,
        "exports": 3,
    },
}

_COVERAGE_ORDER: tuple[str, ...] = (
    "vehicles",
    "drivers",
    "qr",
    "mapping",
    "admin_training",
    "test_incidents",
    "exports",
)

_BLOCKER_ORDER: tuple[str, ...] = (
    "vehicles_target_not_met",
    "drivers_target_not_met",
    "qr_coverage_incomplete",
    "mapping_coverage_incomplete",
    "admin_training_incomplete",
    "test_incidents_incomplete",
    "exports_validation_incomplete",
)

_ACTION_ORDER: dict[str, str] = {
    "vehicles_target_not_met": "Import or activate additional vehicles in org vehicle registry.",
    "drivers_target_not_met": "Import active drivers and verify phone coverage.",
    "qr_coverage_incomplete": "Generate and distribute QR tokens for all active vehicles in scope.",
    "mapping_coverage_incomplete": "Complete external ID mappings for drivers and vehicles.",
    "admin_training_incomplete": "Assign and train at least one org admin for rollout operations.",
    "test_incidents_incomplete": "Run successful test incidents for the current rollout scope.",
    "exports_validation_incomplete": "Complete export validation runs with passing status.",
}


@dataclass(slots=True)
class DeploymentScope:
    scope: DeploymentScopeKey = "pilot"
    scope_version: str = "v1"
    targets: dict[str, int] = field(default_factory=dict)
    readiness_override: ExpansionReadiness | None = None
    source: str = "system"
    captured_at_utc: datetime | None = None


@dataclass(slots=True)
class CoverageMetric:
    key: str
    label: str
    covered: int
    total: int
    percent: int


@dataclass(slots=True)
class DeploymentProgress:
    scope: DeploymentScopeKey
    percent_complete: int
    coverage: list[CoverageMetric] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    recommended_next_actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExpansionReadinessSummary:
    scope: DeploymentScopeKey
    status: ExpansionReadiness
    readiness_score: int
    blockers: list[str] = field(default_factory=list)
    recommended_next_actions: list[str] = field(default_factory=list)
    coverage: list[CoverageMetric] = field(default_factory=list)
    override_applied: bool = False


def _safe_percent(covered: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(max(0.0, min(1.0, covered / total)) * 100)


def _normalize_scope(raw_scope: str | None) -> DeploymentScopeKey:
    if raw_scope in DEPLOYMENT_SCOPE_KEYS:
        return raw_scope
    return "pilot"


def _merge_targets(
    scope: DeploymentScopeKey, incoming: dict[str, int] | None
) -> dict[str, int]:
    merged = {**DEFAULT_TARGETS_BY_SCOPE[scope]}
    for key, value in (incoming or {}).items():
        if key in merged:
            merged[key] = max(1, int(value))
    return merged


def get_deployment_scope(db: Session, *, org_id: uuid.UUID) -> DeploymentScope:
    latest = get_latest_deployment_scope_snapshot(db, org_id)
    if latest is None:
        scope = "pilot"
        return DeploymentScope(scope=scope, targets=_merge_targets(scope, None))

    payload = latest.scope_json or {}
    scope = _normalize_scope(payload.get("scope"))
    return DeploymentScope(
        scope=scope,
        scope_version=latest.scope_version,
        targets=_merge_targets(scope, payload.get("targets")),
        readiness_override=payload.get("readiness_override"),
        source=payload.get("source") or "manual",
        captured_at_utc=latest.captured_at_utc,
    )


def set_deployment_scope(
    db: Session,
    *,
    org_id: uuid.UUID,
    scope: DeploymentScopeKey,
    actor_user_id: uuid.UUID | None,
    targets: dict[str, int] | None = None,
    readiness_override: ExpansionReadiness | None = None,
    source: str = "manual",
) -> DeploymentScope:
    normalized_scope = _normalize_scope(scope)
    merged_targets = _merge_targets(normalized_scope, targets)
    payload = {
        "scope": normalized_scope,
        "targets": merged_targets,
        "readiness_override": readiness_override,
        "source": source,
    }
    snapshot = create_deployment_scope_snapshot(
        db,
        org_id,
        scope_version="v1",
        scope_json=payload,
        captured_by_user_id=actor_user_id,
    )
    return DeploymentScope(
        scope=normalized_scope,
        scope_version=snapshot.scope_version,
        targets=merged_targets,
        readiness_override=readiness_override,
        source=source,
        captured_at_utc=snapshot.captured_at_utc,
    )


def clear_deployment_scope(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    source: str = "manual",
) -> DeploymentScope:
    return set_deployment_scope(
        db,
        org_id=org_id,
        scope="pilot",
        actor_user_id=actor_user_id,
        targets=DEFAULT_TARGETS_BY_SCOPE["pilot"],
        readiness_override=None,
        source=source,
    )


def _coverage_metrics(
    db: Session, *, org_id: uuid.UUID, scope: DeploymentScope
) -> list[CoverageMetric]:
    signals = collect_onboarding_signals(db, org_id=org_id)

    active_driver_count = (
        db.query(func.count(Driver.driver_id))
        .filter(Driver.org_id == org_id, Driver.is_active.is_(True))
        .scalar()
        or 0
    )
    admin_count = (
        db.query(func.count(User.id))
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(
            UserOrg.org_id == org_id, User.is_active.is_(True), User.role == "org_admin"
        )
        .scalar()
        or 0
    )
    successful_test_runs = (
        db.query(func.count(OrgTestIncidentRun.run_id))
        .filter(
            OrgTestIncidentRun.org_id == org_id,
            OrgTestIncidentRun.status == "completed",
        )
        .scalar()
        or 0
    )
    passed_exports = (
        db.query(func.count(OrgExportValidationRun.validation_run_id))
        .filter(
            OrgExportValidationRun.org_id == org_id,
            OrgExportValidationRun.status == "passed",
        )
        .scalar()
        or 0
    )

    target_vehicles = max(1, scope.targets.get("vehicles", 1))
    target_drivers = max(1, scope.targets.get("drivers", 1))
    target_admins = max(1, scope.targets.get("admins", 1))
    target_tests = max(1, scope.targets.get("test_incidents", 1))
    target_exports = max(1, scope.targets.get("exports", 1))

    mapping_total = max(signals.vehicles_total, active_driver_count, 1)

    by_key = {
        "vehicles": CoverageMetric(
            key="vehicles",
            label="Vehicles onboarded",
            covered=min(signals.vehicles_total, target_vehicles),
            total=target_vehicles,
            percent=_safe_percent(signals.vehicles_total, target_vehicles),
        ),
        "drivers": CoverageMetric(
            key="drivers",
            label="Drivers onboarded",
            covered=min(active_driver_count, target_drivers),
            total=target_drivers,
            percent=_safe_percent(active_driver_count, target_drivers),
        ),
        "qr": CoverageMetric(
            key="qr",
            label="QR distribution",
            covered=min(signals.qr_codes_distributed, max(signals.vehicles_total, 1)),
            total=max(signals.vehicles_total, 1),
            percent=_safe_percent(
                signals.qr_codes_distributed, max(signals.vehicles_total, 1)
            ),
        ),
        "mapping": CoverageMetric(
            key="mapping",
            label="External mapping coverage",
            covered=min(signals.mapping_count, mapping_total),
            total=mapping_total,
            percent=_safe_percent(signals.mapping_count, mapping_total),
        ),
        "admin_training": CoverageMetric(
            key="admin_training",
            label="Admin training",
            covered=min(admin_count, target_admins),
            total=target_admins,
            percent=_safe_percent(admin_count, target_admins),
        ),
        "test_incidents": CoverageMetric(
            key="test_incidents",
            label="Test incidents",
            covered=min(successful_test_runs, target_tests),
            total=target_tests,
            percent=_safe_percent(successful_test_runs, target_tests),
        ),
        "exports": CoverageMetric(
            key="exports",
            label="Validated exports",
            covered=min(passed_exports, target_exports),
            total=target_exports,
            percent=_safe_percent(passed_exports, target_exports),
        ),
    }
    return [by_key[key] for key in _COVERAGE_ORDER]


def _derive_blockers_and_actions(
    coverage: list[CoverageMetric],
) -> tuple[list[str], list[str]]:
    by_key = {metric.key: metric for metric in coverage}
    blockers: list[str] = []

    if by_key["vehicles"].percent < 100:
        blockers.append("vehicles_target_not_met")
    if by_key["drivers"].percent < 100:
        blockers.append("drivers_target_not_met")
    if by_key["qr"].percent < 100:
        blockers.append("qr_coverage_incomplete")
    if by_key["mapping"].percent < 100:
        blockers.append("mapping_coverage_incomplete")
    if by_key["admin_training"].percent < 100:
        blockers.append("admin_training_incomplete")
    if by_key["test_incidents"].percent < 100:
        blockers.append("test_incidents_incomplete")
    if by_key["exports"].percent < 100:
        blockers.append("exports_validation_incomplete")

    ordered_blockers = [code for code in _BLOCKER_ORDER if code in blockers]
    actions = [_ACTION_ORDER[code] for code in ordered_blockers]
    return ordered_blockers, actions


def get_deployment_progress(db: Session, *, org_id: uuid.UUID) -> DeploymentProgress:
    scope = get_deployment_scope(db, org_id=org_id)
    coverage = _coverage_metrics(db, org_id=org_id, scope=scope)
    percent = (
        int(sum(metric.percent for metric in coverage) / len(coverage))
        if coverage
        else 0
    )
    blockers, actions = _derive_blockers_and_actions(coverage)
    return DeploymentProgress(
        scope=scope.scope,
        percent_complete=percent,
        coverage=coverage,
        blockers=blockers,
        recommended_next_actions=actions,
    )


def get_expansion_readiness(
    db: Session, *, org_id: uuid.UUID
) -> ExpansionReadinessSummary:
    scope = get_deployment_scope(db, org_id=org_id)
    progress = get_deployment_progress(db, org_id=org_id)

    status: ExpansionReadiness
    if progress.percent_complete == 0:
        status = "not_started"
    elif progress.blockers:
        status = "blocked"
    elif scope.scope == "pilot":
        status = "pilot_ready"
    else:
        status = "scale_ready"

    if progress.percent_complete > 0 and status == "not_started":
        status = "planning"

    override_applied = False
    if scope.readiness_override in EXPANSION_READINESS_STATES:
        status = scope.readiness_override
        override_applied = True

    summary = ExpansionReadinessSummary(
        scope=scope.scope,
        status=status,
        readiness_score=progress.percent_complete,
        blockers=progress.blockers,
        recommended_next_actions=progress.recommended_next_actions,
        coverage=progress.coverage,
        override_applied=override_applied,
    )

    upsert_expansion_readiness_snapshot(
        db,
        org_id,
        scope_key=scope.scope,
        status=summary.status,
        readiness_score=summary.readiness_score,
        summary_json={
            "blockers": summary.blockers,
            "recommended_next_actions": summary.recommended_next_actions,
            "override_applied": summary.override_applied,
            "computed_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    return summary
