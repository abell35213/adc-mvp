"""Explicit state-machine validators for incident/export status transitions."""

from __future__ import annotations

from fastapi import HTTPException, status

INCIDENT_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"evidence_capturing", "closed"},
    "evidence_capturing": {"closed"},
    "closed": set(),
}

EXPORT_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "requested": {"queued", "processing", "failed"},
    "queued": {"processing", "failed", "expired"},
    "processing": {"ready", "failed", "expired"},
    "ready": {"expired"},
    "failed": {"requested"},
    "expired": set(),
}


def validate_incident_transition(*, current_status: str, next_status: str, actor: str) -> None:
    if current_status == next_status:
        return
    allowed = INCIDENT_ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid incident status transition for {actor}: "
                f"{current_status} -> {next_status}"
            ),
        )


def validate_export_transition(*, current_status: str, next_status: str, actor: str) -> None:
    if current_status == next_status:
        return
    allowed = EXPORT_ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid export status transition for {actor}: "
                f"{current_status} -> {next_status}"
            ),
        )
