"""Typed structures for case completeness, blockers, readiness, and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

CompletenessStatus = Literal["incomplete", "partial", "mostly_complete", "complete"]
BlockerSeverity = Literal["critical", "important", "optional"]
ReadinessState = Literal[
    "not_ready",
    "conditionally_ready",
    "ready_for_export",
    "exported",
    "closed",
]
CaseStatus = Literal[
    "new",
    "in_review",
    "awaiting_evidence",
    "awaiting_follow_up",
    "ready_for_export",
    "exported",
    "escalated",
    "closed",
]


@dataclass(slots=True)
class CompletenessDimensionScore:
    name: str
    earned: int
    possible: int
    percent: int
    status: CompletenessStatus
    missing_items: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CaseCompleteness:
    percent: int
    status: CompletenessStatus
    dimensions: list[CompletenessDimensionScore] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CaseBlocker:
    code: str
    message: str
    severity: BlockerSeverity


@dataclass(slots=True)
class BlockerSummary:
    total: int
    critical_count: int
    important_count: int
    optional_count: int
    items: list[CaseBlocker] = field(default_factory=list)


@dataclass(slots=True)
class CaseReadiness:
    state: ReadinessState
    is_ready_for_export: bool
    completeness_percent: int
    completeness_status: CompletenessStatus
    blockers: BlockerSummary


@dataclass(slots=True)
class CaseOpsSnapshot:
    completeness: CaseCompleteness
    blockers: BlockerSummary
    readiness: CaseReadiness


@dataclass(slots=True)
class AgingMetrics:
    average_age_days: float
    p95_age_days: float
    over_24h: int
    over_72h: int
    over_7d: int


@dataclass(slots=True)
class DashboardMetrics:
    total_open_cases: int
    not_ready_cases: int
    conditionally_ready_cases: int
    ready_for_export_cases: int
    exported_cases: int
    closed_cases: int
    cases_with_critical_blockers: int
    cases_with_important_blockers: int
    aging: AgingMetrics


@dataclass(slots=True)
class TransitionValidationResult:
    allowed: bool
    from_status: CaseStatus
    to_status: CaseStatus
    reason: str | None = None
    validated_at_utc: datetime | None = None
