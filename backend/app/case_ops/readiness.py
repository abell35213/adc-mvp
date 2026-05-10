"""Case readiness state derivation."""

from __future__ import annotations

from typing import cast

from app.case_ops.models import BlockerSummary, CaseReadiness, CaseStatus, CompletenessStatus, ReadinessState


def derive_readiness_state(
    *,
    case_status: str,
    completeness_percent: int,
    completeness_status: str,
    blockers: BlockerSummary,
) -> CaseReadiness:
    normalized_case_status = cast(CaseStatus, str(case_status))

    if normalized_case_status == "closed":
        state: ReadinessState = "closed"
    elif normalized_case_status == "exported":
        state = "exported"
    elif blockers.readiness_blocker_codes and blockers.critical_count > 0:
        state = "not_ready"
    elif blockers.readiness_blocker_codes or completeness_percent < 90:
        state = "conditionally_ready"
    else:
        state = "ready_for_export"

    normalized_completeness_status = cast(CompletenessStatus, str(completeness_status))

    return CaseReadiness(
        state=state,
        is_ready_for_export=state in {"ready_for_export", "exported", "closed"},
        completeness_percent=completeness_percent,
        completeness_status=normalized_completeness_status,
        blockers=blockers,
        blocking_codes=list(blockers.readiness_blocker_codes),
    )
