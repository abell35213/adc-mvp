"""Queue FMCSA driver-violation-history capture for an incident.

This is the third capture pipeline (alongside dashcam + telematics)
fired by :class:`IncidentEvidenceOrchestrator`.

The flow is:

1. Create one ``EvidenceRequest`` (provider=``fmcsa``,
   domain=``inspections``, external_reference=usdot_number).
2. Create one ``IntegrationOperation`` (capability/domain=``inspections``).
3. Enqueue the Celery task ``capture_driver_violation_history``.

The task is responsible for the cache-check, FMCSA pull, attribution
matcher, and writing the ``incident_driver_violation_history`` rows.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.repo.evidence_requests import create_evidence_request
from app.db.repo.integration_operations import create_integration_operation
from app.services.integration_health_service import (
    set_evidence_request_status,
    transition_operation_status,
)


def queue_driver_violation_history_capture(
    db: Session,
    *,
    org_id: uuid.UUID,
    incident_id: uuid.UUID,
    adc_driver_id: str | None,
    usdot_number: str,
    api_correlation_id: str,
) -> uuid.UUID:
    """Create the EvidenceRequest + IntegrationOperation and enqueue the task.

    Returns the new operation_id so the orchestrator can include it in the
    ``EVIDENCE_CAPTURE_ATTEMPTED`` payload.
    """
    operation_correlation_id = f"{api_correlation_id}:inspections"
    operation = create_integration_operation(
        db,
        org_id=org_id,
        incident_id=incident_id,
        provider="fmcsa",
        domain="inspections",
        operation_type="capture_driver_violation_history",
        status="queued",
        correlation_id=operation_correlation_id,
        external_reference=usdot_number,
        payload_json={
            "usdot_number": usdot_number,
            "adc_driver_id": adc_driver_id,
        },
    )
    transition_operation_status(
        db,
        operation=operation,
        to_status="queued",
        message="FMCSA driver violation history capture queued",
    )

    evidence_request = create_evidence_request(
        db,
        org_id=org_id,
        incident_id=incident_id,
        operation_id=operation.operation_id,
        provider="fmcsa",
        domain="inspections",
        status="open",
        correlation_id=operation_correlation_id,
        external_reference=usdot_number,
        request_payload_json={
            "usdot_number": usdot_number,
            "adc_driver_id": adc_driver_id,
        },
    )
    set_evidence_request_status(
        db, evidence_request=evidence_request, status="in_progress"
    )

    # Import lazily to avoid importing celery_app at module-import time
    # (keeps tests able to monkeypatch the underlying task).
    from app.tasks.evidence_tasks import capture_driver_violation_history

    capture_driver_violation_history.delay(
        operation_id=str(operation.operation_id),
        evidence_request_id=str(evidence_request.evidence_request_id),
        org_id=str(org_id),
        incident_id=str(incident_id),
        adc_driver_id=adc_driver_id,
        usdot_number=usdot_number,
    )
    return operation.operation_id
