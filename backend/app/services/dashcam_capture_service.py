"""Queue dashcam evidence capture operations."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import EvidenceRequest
from app.db.repo.integration_operations import create_integration_operation
from app.services.integration_health_service import (
    set_evidence_request_status,
    transition_operation_status,
)
from app.tasks.evidence_tasks import capture_dashcam


def queue_dashcam_capture(
    db: Session,
    *,
    org_id: uuid.UUID,
    incident_id: uuid.UUID,
    window_start: str | None,
    window_end: str | None,
    api_correlation_id: str,
    evidence_request_ids: list[uuid.UUID],
) -> uuid.UUID:
    """Create and queue dashcam capture operation."""
    operation_correlation_id = f"{api_correlation_id}:dashcam"
    operation = create_integration_operation(
        db,
        org_id=org_id,
        incident_id=incident_id,
        provider="samsara",
        domain="dashcam",
        operation_type="capture_dashcam",
        status="requested",
        correlation_id=operation_correlation_id,
        payload_json={
            "window_start": window_start,
            "window_end": window_end,
            "evidence_request_ids": [str(er_id) for er_id in evidence_request_ids],
        },
    )
    transition_operation_status(
        db,
        operation=operation,
        to_status="requested",
        message="Dashcam capture operation requested",
    )
    evidence_requests = (
        db.query(EvidenceRequest)
        .filter(EvidenceRequest.evidence_request_id.in_(evidence_request_ids))
        .all()
    )
    for evidence_request in evidence_requests:
        evidence_request.operation_id = operation.operation_id
        db.add(evidence_request)
    db.commit()

    for evidence_request in evidence_requests:
        set_evidence_request_status(db, evidence_request=evidence_request, status="in_progress")

    capture_dashcam.delay(
        str(incident_id),
        window_start,
        window_end,
        operation_id=str(operation.operation_id),
        correlation_id=operation_correlation_id,
    )
    return operation.operation_id
