"""Case completeness scoring helpers."""

from __future__ import annotations

from app.case_ops.models import (
    CaseCompleteness,
    CompletenessDimensionScore,
    CompletenessStatus,
)


def _status_for_percent(percent: int) -> CompletenessStatus:
    if percent >= 100:
        return "complete"
    if percent >= 75:
        return "mostly_complete"
    if percent >= 40:
        return "partial"
    return "incomplete"


def _calc_percent(earned: int, possible: int) -> int:
    if possible <= 0:
        return 100
    return max(0, min(100, round((earned / possible) * 100)))


def score_dimensions(*, artifacts: list, events: list, exports: list) -> list[CompletenessDimensionScore]:
    captured = sum(1 for artifact in artifacts if artifact.status == "captured")
    possible_artifacts = len(artifacts)
    missing_artifacts = [
        f"artifact:{artifact.artifact_type}:{artifact.status}"
        for artifact in artifacts
        if artifact.status != "captured"
    ]
    artifact_percent = _calc_percent(captured, possible_artifacts)

    event_types = [str(getattr(event, "event_type", "")).lower() for event in events]
    collected = any("capture" in event_type or "incident_started" in event_type for event_type in event_types)
    validated = any("hash" in event_type or "validat" in event_type for event_type in event_types)
    exported = any("export" in event_type for event_type in event_types)
    timeline_checks = [collected, validated, exported]
    timeline_percent = _calc_percent(sum(1 for passed in timeline_checks if passed), len(timeline_checks))
    missing_timeline = [
        label
        for ok, label in (
            (collected, "timeline:collection"),
            (validated, "timeline:validation"),
            (exported, "timeline:export"),
        )
        if not ok
    ]

    has_ready_export = any(export.status == "ready" for export in exports)
    export_percent = 100 if has_ready_export else 0
    missing_export = [] if has_ready_export else ["export:ready_package"]

    return [
        CompletenessDimensionScore(
            name="evidence_capture",
            earned=captured,
            possible=possible_artifacts,
            percent=artifact_percent,
            status=_status_for_percent(artifact_percent),
            missing_items=missing_artifacts,
        ),
        CompletenessDimensionScore(
            name="custody_timeline",
            earned=sum(1 for passed in timeline_checks if passed),
            possible=len(timeline_checks),
            percent=timeline_percent,
            status=_status_for_percent(timeline_percent),
            missing_items=missing_timeline,
        ),
        CompletenessDimensionScore(
            name="export_readiness",
            earned=1 if has_ready_export else 0,
            possible=1,
            percent=export_percent,
            status=_status_for_percent(export_percent),
            missing_items=missing_export,
        ),
    ]


def calculate_completeness(*, artifacts: list, events: list, exports: list) -> CaseCompleteness:
    dimensions = score_dimensions(artifacts=artifacts, events=events, exports=exports)
    weights = {
        "evidence_capture": 0.6,
        "custody_timeline": 0.25,
        "export_readiness": 0.15,
    }
    percent = round(sum(d.percent * weights.get(d.name, 0.0) for d in dimensions))
    missing_items: list[str] = []
    for dimension in dimensions:
        missing_items.extend(dimension.missing_items)

    return CaseCompleteness(
        percent=percent,
        status=_status_for_percent(percent),
        dimensions=dimensions,
        missing_items=missing_items,
    )
