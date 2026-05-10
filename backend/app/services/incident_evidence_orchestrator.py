"""Orchestrates incident evidence request creation and capture queueing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import MetricNames, increment, timed
from app.db.models import Incident, Org
from app.db.repo.evidence_requests import create_evidence_request
from app.domain.system_event_types import SystemEventType
from app.services.dashcam_capture_service import queue_dashcam_capture
from app.services.driver_violation_history_capture_service import (
    queue_driver_violation_history_capture,
)
from app.services.messaging_service import emit_timeline_event
from app.services.telematics_capture_service import queue_telematics_capture


@dataclass
class IncidentEvidenceOrchestrationResult:
    """Result of evidence orchestration for incident creation."""

    correlation_id: str
    dashcam_operation_id: uuid.UUID
    telematics_operation_id: uuid.UUID
    inspections_operation_id: uuid.UUID | None = None


class IncidentEvidenceOrchestrator:
    """Creates evidence requests first, then queues provider operations."""

    def __init__(self, db: Session):
        self.db = db

    def begin_capture(
        self,
        *,
        org_id: uuid.UUID,
        incident_id: uuid.UUID,
        actor_id: str,
        actor_type: str,
        window_start: str | None,
        window_end: str | None,
        correlation_id: str,
    ) -> IncidentEvidenceOrchestrationResult:
        with timed(MetricNames.INTEGRATION_PROVIDER_LATENCY):
            dashcam_request_ids = [
                create_evidence_request(
                    self.db,
                    org_id=org_id,
                    incident_id=incident_id,
                    provider="samsara",
                    domain="dashcam",
                    external_reference=stream,
                    status="open",
                    correlation_id=f"{correlation_id}:dashcam",
                    request_payload_json={
                        "stream": stream,
                        "window_start": window_start,
                        "window_end": window_end,
                    },
                ).evidence_request_id
                for stream in ("road_facing", "driver_facing")
            ]
            telematics_request_ids = [
                create_evidence_request(
                    self.db,
                    org_id=org_id,
                    incident_id=incident_id,
                    provider="samsara",
                    domain="telematics",
                    external_reference=dataset,
                    status="open",
                    correlation_id=f"{correlation_id}:telematics",
                    request_payload_json={
                        "dataset": dataset,
                        "window_start": window_start,
                        "window_end": window_end,
                    },
                ).evidence_request_id
                for dataset in ("eld", "gps", "safety_events", "vehicle_state")
            ]

        increment(MetricNames.INTEGRATION_PROVIDER_REQUESTS, len(dashcam_request_ids))
        increment(MetricNames.INTEGRATION_PROVIDER_REQUESTS, len(telematics_request_ids))

        emit_timeline_event(
            self.db,
            incident_id=incident_id,
            event_type=SystemEventType.EVIDENCE_CAPTURE_REQUESTED,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "correlation_id": correlation_id,
                "window_start": window_start,
                "window_end": window_end,
                "dashcam_request_ids": [str(v) for v in dashcam_request_ids],
                "telematics_request_ids": [str(v) for v in telematics_request_ids],
            },
        )

        dashcam_operation_id = queue_dashcam_capture(
            self.db,
            org_id=org_id,
            incident_id=incident_id,
            window_start=window_start,
            window_end=window_end,
            api_correlation_id=correlation_id,
            evidence_request_ids=dashcam_request_ids,
        )
        telematics_operation_id = queue_telematics_capture(
            self.db,
            org_id=org_id,
            incident_id=incident_id,
            window_start=window_start,
            window_end=window_end,
            api_correlation_id=correlation_id,
            evidence_request_ids=telematics_request_ids,
        )

        # ── Optional 3rd capture: FMCSA driver violation history ──
        inspections_operation_id: uuid.UUID | None = None
        if getattr(settings, "FMCSA_INSPECTIONS_ENABLED", True):
            org = self.db.query(Org).filter(Org.id == org_id).first()
            usdot = (org.usdot_number if org is not None else None) or ""
            usdot = usdot.strip()
            if usdot:
                incident = (
                    self.db.query(Incident)
                    .filter(Incident.incident_id == incident_id)
                    .first()
                )
                inspections_operation_id = queue_driver_violation_history_capture(
                    self.db,
                    org_id=org_id,
                    incident_id=incident_id,
                    adc_driver_id=(
                        cast(str | None, incident.adc_driver_id) if incident is not None else None
                    ),
                    usdot_number=usdot,
                    api_correlation_id=correlation_id,
                )

        emit_timeline_event(
            self.db,
            incident_id=incident_id,
            event_type=SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "correlation_id": correlation_id,
                "dashcam_operation_id": str(dashcam_operation_id),
                "telematics_operation_id": str(telematics_operation_id),
                "inspections_operation_id": (
                    str(inspections_operation_id) if inspections_operation_id else None
                ),
            },
        )
        return IncidentEvidenceOrchestrationResult(
            correlation_id=correlation_id,
            dashcam_operation_id=dashcam_operation_id,
            telematics_operation_id=telematics_operation_id,
            inspections_operation_id=inspections_operation_id,
        )
