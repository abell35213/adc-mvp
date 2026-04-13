"""Case workflow transition validator."""

from __future__ import annotations

from datetime import datetime, timezone

from app.case_ops.models import TransitionValidationResult

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"in_review", "awaiting_evidence", "closed", "escalated"},
    "in_review": {"awaiting_evidence", "awaiting_follow_up", "ready_for_export", "escalated", "closed"},
    "awaiting_evidence": {"in_review", "awaiting_follow_up", "closed", "escalated"},
    "awaiting_follow_up": {"in_review", "ready_for_export", "closed", "escalated"},
    "ready_for_export": {"exported", "awaiting_follow_up", "closed", "escalated"},
    "exported": {"closed", "escalated"},
    "escalated": {"in_review", "awaiting_follow_up", "ready_for_export", "closed"},
    "closed": set(),
}


def validate_transition(from_status: str, to_status: str) -> TransitionValidationResult:
    source = str(from_status)
    target = str(to_status)

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

    if target not in allowed_targets:
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
