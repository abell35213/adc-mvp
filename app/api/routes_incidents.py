"""Incident API routes."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ArtifactSummary,
    CreateExportResponse,
    CreateIncidentRequest,
    CreateIncidentResponse,
    ExportSummary,
    IncidentDetailResponse,
)
from app.db.session import get_db
from app.db.repo_incidents import create_incident, get_incident, list_incidents
from app.db.repo_events import create_event
from app.db.repo_artifacts import get_artifacts_by_incident
from app.db.repo_exports import create_export, get_exports_by_incident
from app.domain.system_event_types import SystemEventType
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics
from app.tasks.export_tasks import generate_export

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def list_incidents_endpoint(db: Session = Depends(get_db)):
    return list_incidents(db)


@router.post("/", response_model=CreateIncidentResponse, status_code=201)
def create_incident_endpoint(
    body: CreateIncidentRequest,
    db: Session = Depends(get_db),
):
    # 1. Create the incident record
    incident = create_incident(
        db,
        status="evidence_capturing",
        adc_vehicle_id=body.adc_vehicle_id,
        samsara_vehicle_id=body.samsara_vehicle_id,
        adc_driver_id=body.adc_driver_id,
        severity=body.severity,
    )

    incident_id = incident.incident_id

    # 2. Write INCIDENT_STARTED event
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.INCIDENT_STARTED,
        actor_type="system",
        actor_id="api",
        payload={
            "severity": body.severity,
            "adc_vehicle_id": body.adc_vehicle_id,
            "samsara_vehicle_id": body.samsara_vehicle_id,
            "adc_driver_id": body.adc_driver_id,
        },
    )

    # 3. Write EVIDENCE_LOCKDOWN_STARTED event
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.EVIDENCE_LOCKDOWN_STARTED,
        actor_type="system",
        actor_id="api",
    )

    # 4. Enqueue Celery evidence-capture workflow
    str_id = str(incident_id)
    capture_dashcam.delay(str_id)
    capture_telematics.delay(str_id)

    return CreateIncidentResponse(
        incident_id=incident_id,
        status=incident.status,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_endpoint(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    artifacts = get_artifacts_by_incident(db, incident_id)
    exports = get_exports_by_incident(db, incident_id)

    return IncidentDetailResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        severity=incident.severity,
        adc_vehicle_id=incident.adc_vehicle_id,
        samsara_vehicle_id=incident.samsara_vehicle_id,
        adc_driver_id=incident.adc_driver_id,
        evidence_inventory=[
            ArtifactSummary(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                status=a.status,
            )
            for a in artifacts
        ],
        export_status=[
            ExportSummary(export_id=e.export_id, status=e.status)
            for e in exports
        ],
    )


@router.post(
    "/{incident_id}/exports",
    response_model=CreateExportResponse,
    status_code=201,
)
def request_export_endpoint(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    incident = get_incident(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    export = create_export(db, incident_id=incident_id, status="requested")

    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.EXPORT_REQUESTED,
        actor_type="system",
        actor_id="api",
        payload={"export_id": str(export.export_id)},
    )

    generate_export.delay(str(export.export_id), str(incident_id))

    return CreateExportResponse(
        export_id=export.export_id,
        status=export.status,
    )
