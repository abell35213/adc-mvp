"""Blocker detection for case operations workflows."""

from __future__ import annotations

from app.case_ops.models import BlockerSummary, CaseBlocker


def detect_blockers(*, artifacts: list, events: list, exports: list) -> BlockerSummary:
    blockers: list[CaseBlocker] = []

    pending_artifacts = [artifact for artifact in artifacts if artifact.status == "pending"]
    unavailable_artifacts = [artifact for artifact in artifacts if artifact.status == "unavailable"]
    captured_count = sum(1 for artifact in artifacts if artifact.status == "captured")

    if pending_artifacts:
        blockers.append(
            CaseBlocker(
                code="evidence_capture_incomplete",
                message=f"{len(pending_artifacts)} evidence artifact(s) still pending capture.",
                severity="critical",
            )
        )
    if captured_count == 0 and artifacts:
        blockers.append(
            CaseBlocker(
                code="no_captured_evidence",
                message="No captured evidence is available yet.",
                severity="critical",
            )
        )
    if unavailable_artifacts:
        blockers.append(
            CaseBlocker(
                code="evidence_unavailable",
                message=f"{len(unavailable_artifacts)} evidence artifact(s) marked unavailable.",
                severity="important",
            )
        )

    event_types = [str(getattr(event, "event_type", "")).lower() for event in events]
    validated = any("hash" in event_type or "validat" in event_type for event_type in event_types)
    if not validated:
        blockers.append(
            CaseBlocker(
                code="timeline_validation_missing",
                message="No validation/hash timeline event detected.",
                severity="important",
            )
        )

    if not exports:
        blockers.append(
            CaseBlocker(
                code="export_not_requested",
                message="No export request has been created yet.",
                severity="optional",
            )
        )
    elif not any(export.status == "ready" for export in exports):
        blockers.append(
            CaseBlocker(
                code="export_not_ready",
                message="Export exists but no package is marked ready.",
                severity="optional",
            )
        )

    critical_count = sum(1 for blocker in blockers if blocker.severity == "critical")
    important_count = sum(1 for blocker in blockers if blocker.severity == "important")
    optional_count = sum(1 for blocker in blockers if blocker.severity == "optional")
    return BlockerSummary(
        total=len(blockers),
        critical_count=critical_count,
        important_count=important_count,
        optional_count=optional_count,
        items=blockers,
    )
