"""Blocker detection for case operations workflows."""

from __future__ import annotations

from app.case_ops.models import BlockerSeverity, BlockerSummary, CaseBlocker, MissingItem, MissingItemCategory


def _category_for_artifact(artifact_type: str) -> MissingItemCategory:
    normalized = artifact_type.lower()
    if "dash" in normalized and "cam" in normalized:
        return "dashcam"
    if "telem" in normalized or "gps" in normalized or "can" in normalized:
        return "telematics"
    if "driver" in normalized or "statement" in normalized:
        return "driver_input"
    if "document" in normalized or "report" in normalized or "pdf" in normalized:
        return "document"
    if "video" in normalized or "photo" in normalized or "image" in normalized or "media" in normalized:
        return "media"
    return "internal_review"


def _build_blocker(
    *,
    code: str,
    message: str,
    severity: BlockerSeverity,
    category: MissingItemCategory,
    resolvable_by: str,
    action_hint: str,
    blocks_readiness: bool,
) -> CaseBlocker:
    missing_item = MissingItem(
        code=code,
        category=category,
        severity=severity,
        message=message,
        resolvableBy=resolvable_by,
        actionHint=action_hint,
    )
    return CaseBlocker(
        code=code,
        message=message,
        severity=severity,
        missing_item=missing_item,
        blocks_readiness=blocks_readiness,
    )


def detect_blockers(*, artifacts: list, events: list, exports: list) -> BlockerSummary:
    blockers: list[CaseBlocker] = []

    pending_artifacts = [artifact for artifact in artifacts if artifact.status == "pending"]
    unavailable_artifacts = [artifact for artifact in artifacts if artifact.status == "unavailable"]
    captured_count = sum(1 for artifact in artifacts if artifact.status == "captured")

    if pending_artifacts:
        category = _category_for_artifact(str(getattr(pending_artifacts[0], "artifact_type", "internal_review")))
        blockers.append(
            _build_blocker(
                code="evidence_capture_incomplete",
                message=f"{len(pending_artifacts)} evidence artifact(s) still pending capture.",
                severity="critical",
                category=category,
                resolvable_by="evidence_ops",
                action_hint="Capture or ingest pending evidence artifacts before review handoff.",
                blocks_readiness=True,
            )
        )
    if captured_count == 0 and artifacts:
        blockers.append(
            _build_blocker(
                code="no_captured_evidence",
                message="No captured evidence is available yet.",
                severity="critical",
                category="internal_review",
                resolvable_by="incident_response",
                action_hint="Confirm device connectivity and capture at least one required artifact.",
                blocks_readiness=True,
            )
        )
    if unavailable_artifacts:
        category = _category_for_artifact(str(getattr(unavailable_artifacts[0], "artifact_type", "internal_review")))
        blockers.append(
            _build_blocker(
                code="evidence_unavailable",
                message=f"{len(unavailable_artifacts)} evidence artifact(s) marked unavailable.",
                severity="important",
                category=category,
                resolvable_by="evidence_ops",
                action_hint="Retry evidence pull or document alternate source coverage.",
                blocks_readiness=True,
            )
        )

    event_types = [str(getattr(event, "event_type", "")).lower() for event in events]
    validated = any("hash" in event_type or "validat" in event_type for event_type in event_types)
    if not validated:
        blockers.append(
            _build_blocker(
                code="timeline_validation_missing",
                message="No validation/hash timeline event detected.",
                severity="important",
                category="internal_review",
                resolvable_by="case_reviewer",
                action_hint="Run timeline validation and record hash verification event.",
                blocks_readiness=True,
            )
        )

    if not exports:
        blockers.append(
            _build_blocker(
                code="export_not_requested",
                message="No export request has been created yet.",
                severity="optional",
                category="document",
                resolvable_by="case_reviewer",
                action_hint="Create an export request when legal packet generation is needed.",
                blocks_readiness=False,
            )
        )
    elif not any(export.status == "ready" for export in exports):
        blockers.append(
            _build_blocker(
                code="export_not_ready",
                message="Export exists but no package is marked ready.",
                severity="optional",
                category="document",
                resolvable_by="export_pipeline",
                action_hint="Allow export processing to complete or retry failed export jobs.",
                blocks_readiness=False,
            )
        )

    critical_count = sum(1 for blocker in blockers if blocker.severity == "critical")
    important_count = sum(1 for blocker in blockers if blocker.severity == "important")
    optional_count = sum(1 for blocker in blockers if blocker.severity == "optional")
    readiness_blockers = [blocker.code for blocker in blockers if blocker.blocks_readiness]
    return BlockerSummary(
        total=len(blockers),
        critical_count=critical_count,
        important_count=important_count,
        optional_count=optional_count,
        readiness_blocker_codes=readiness_blockers,
        items=blockers,
    )
