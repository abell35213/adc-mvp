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
    EventSummary,
    ExportSummary,
    IncidentDetailResponse,
    IncidentListItem,
)
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.db.repo.incidents import create_incident, get_incident, list_incidents
from app.db.repo.events import create_event, get_events_by_incident
from app.db.repo.artifacts import get_artifacts_by_incident
from app.db.repo.exports import create_export, get_exports_by_incident
from app.db.repo.users import get_user_org_ids
from app.domain.system_event_types import SystemEventType
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.export_tasks import build_export

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[IncidentListItem])
def list_incidents_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_ids = get_user_org_ids(db, current_user.id)
    incidents = list_incidents(db, org_ids=org_ids)
    result = []
    for inc in incidents:
        artifacts = get_artifacts_by_incident(db, inc.incident_id)
        captured = sum(1 for a in artifacts if a.status == "captured")
        result.append(
            IncidentListItem(
                incident_id=inc.incident_id,
                status=inc.status,
                severity=inc.severity,
                adc_vehicle_id=inc.adc_vehicle_id,
                samsara_vehicle_id=inc.samsara_vehicle_id,
                adc_driver_id=inc.adc_driver_id,
                created_at_utc=inc.created_at_utc.isoformat()
                if inc.created_at_utc
                else None,
                evidence_captured=captured,
                evidence_total=len(artifacts),
            )
        )
    return result


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
    events = get_events_by_incident(db, incident_id)

    return IncidentDetailResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        severity=incident.severity,
        adc_vehicle_id=incident.adc_vehicle_id,
        samsara_vehicle_id=incident.samsara_vehicle_id,
        adc_driver_id=incident.adc_driver_id,
        created_at_utc=incident.created_at_utc.isoformat()
        if incident.created_at_utc
        else None,
        evidence_inventory=[
            ArtifactSummary(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                status=a.status,
                captured_at_utc=(
                    a.capture_window_end_utc.isoformat()
                    if a.capture_window_end_utc
                    else None
                ),
                unavailable_reason=a.unavailable_reason_code,
            )
            for a in artifacts
        ],
        export_status=[
            ExportSummary(
                export_id=e.export_id,
                status=e.status,
                created_at_utc=e.created_at_utc.isoformat()
                if e.created_at_utc
                else None,
            )
            for e in exports
        ],
        timeline=[
            EventSummary(
                event_type=ev.event_type,
                occurred_at_utc=ev.occurred_at_utc.isoformat()
                if ev.occurred_at_utc
                else "",
                actor_type=ev.actor_type,
                payload=ev.payload,
            )
            for ev in sorted(events, key=lambda e: e.occurred_at_utc or "")
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

    export = create_export(
        db,
        incident_id=incident_id,
        org_id=incident.org_id,
        status="requested",
    )

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
