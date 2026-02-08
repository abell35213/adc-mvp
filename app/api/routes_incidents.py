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
from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.db.repo_incidents import create_incident, get_incident, list_incidents
from app.db.repo_events import create_event
from app.db.repo_artifacts import get_artifacts_by_incident
from app.db.repo_exports import create_export, get_exports_by_incident
from app.db.repo_users import get_user_org_ids
from app.domain.system_event_types import SystemEventType
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.export_tasks import build_export

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
def list_incidents_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    return list_incidents(db, org_ids=org_ids)


@router.post("/", response_model=CreateIncidentResponse, status_code=201)
def create_incident_endpoint(
    body: CreateIncidentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Use the first org the user belongs to
    org_ids = get_user_org_ids(db, current_user.id)
    org_id = org_ids[0] if org_ids else None

    # 1. Create the incident record
    incident = create_incident(
        db,
        status="evidence_capturing",
        adc_vehicle_id=body.adc_vehicle_id,
        samsara_vehicle_id=body.samsara_vehicle_id,
        adc_driver_id=body.adc_driver_id,
        severity=body.severity,
        org_id=org_id,
    )

    incident_id = incident.incident_id

    # 2. Write INCIDENT_STARTED event
    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.INCIDENT_STARTED,
        actor_type="user",
        actor_id=str(current_user.id),
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
        actor_type="user",
        actor_id=str(current_user.id),
    )

    # 4. Enqueue Celery evidence-capture workflow
    str_id = str(incident_id)
    window_start = body.window_start or ""
    window_end = body.window_end or ""
    capture_dashcam.delay(str_id, window_start, window_end)
    capture_telematics_bundle.delay(str_id, window_start, window_end)

    return CreateIncidentResponse(
        incident_id=incident_id,
        status=incident.status,
    )


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_endpoint(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    incident = get_incident(db, incident_id, org_ids=org_ids)
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
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    export = create_export(db, incident_id=incident_id, status="requested")

    create_event(
        db,
        incident_id=incident_id,
        event_type=SystemEventType.EXPORT_REQUESTED,
        actor_type="user",
        actor_id=str(current_user.id),
        payload={"export_id": str(export.export_id)},
    )

    build_export.delay(str(incident_id), str(export.export_id))

    return CreateExportResponse(
        export_id=export.export_id,
        status=export.status,
    )
