"""Case workflow transition validator."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import cast

from app.case_ops.models import CaseStatus, TransitionValidationResult

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"in_review", "awaiting_evidence"},
    "in_review": {"awaiting_evidence", "awaiting_follow_up", "ready_for_export"},
    "awaiting_evidence": {"in_review", "awaiting_follow_up"},
    "awaiting_follow_up": {"in_review", "ready_for_export"},
    "ready_for_export": {"exported", "awaiting_follow_up"},
    "exported": set(),
    "escalated": {"in_review", "awaiting_follow_up", "ready_for_export"},
    "closed": set(),
}

_PRIVILEGED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"closed", "escalated"},
    "in_review": {"closed", "escalated"},
    "awaiting_evidence": {"closed", "escalated"},
    "awaiting_follow_up": {"closed", "escalated"},
    "ready_for_export": {"closed", "escalated"},
    "exported": {"closed", "escalated"},
    "escalated": {"closed"},
    "closed": {"in_review"},
}


def validate_transition(
    from_status: str, to_status: str, *, allow_privileged: bool = False
) -> TransitionValidationResult:
    source = _as_case_status(str(from_status))
    target = _as_case_status(str(to_status))

    if source is None:
        return TransitionValidationResult(
            allowed=False,
            from_status="new",
            to_status=target or "new",
            reason=f"Unknown source status '{from_status}'.",
            validated_at_utc=datetime.now(timezone.utc),
        )

    if target is None:
        return TransitionValidationResult(
            allowed=False,
            from_status=source,
            to_status="new",
            reason=f"Unknown target status '{to_status}'.",
            validated_at_utc=datetime.now(timezone.utc),
        )

    if source == target:
        return TransitionValidationResult(
            allowed=True,
            from_status=source,
            to_status=target,
            reason="No-op transition.",
            validated_at_utc=datetime.now(timezone.utc),
        )

    allowed_targets = _ALLOWED_TRANSITIONS.get(source)
    if allowed_targets is None:
        return TransitionValidationResult(
            allowed=False,
            from_status=source,
            to_status=target,
            reason=f"Unknown source status '{source}'.",
            validated_at_utc=datetime.now(timezone.utc),
        )

    if target in allowed_targets:
        return TransitionValidationResult(
            allowed=True,
            from_status=source,
            to_status=target,
            validated_at_utc=datetime.now(timezone.utc),
        )

    privileged_targets = _PRIVILEGED_TRANSITIONS.get(source, set())
    if target in privileged_targets and not allow_privileged:
        return TransitionValidationResult(
            allowed=False,
            from_status=source,
            to_status=target,
            reason=(
                f"Transition from '{source}' to '{target}' is privileged and requires "
                "explicit permission."
            ),
            validated_at_utc=datetime.now(timezone.utc),
        )

    if target not in privileged_targets:
        return TransitionValidationResult(
            allowed=False,
            from_status=source,
            to_status=target,
            reason=f"Transition from '{source}' to '{target}' is not permitted.",
            validated_at_utc=datetime.now(timezone.utc),
        )

    return TransitionValidationResult(
        allowed=True,
        from_status=source,
        to_status=target,
        validated_at_utc=datetime.now(timezone.utc),
    )


_ALL_CASE_STATUSES: set[CaseStatus] = {
    "new",
    "in_review",
    "awaiting_evidence",
    "awaiting_follow_up",
    "ready_for_export",
    "exported",
    "escalated",
    "closed",
}


def _as_case_status(value: str) -> CaseStatus | None:
    return cast(CaseStatus, value) if value in _ALL_CASE_STATUSES else None
