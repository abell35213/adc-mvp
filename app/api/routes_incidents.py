"""Incident API routes.

This module defines API endpoints for listing incidents, creating new
incidents, retrieving incident details, and requesting export packages. It
extends the upstream implementation to integrate Twilio voice and SMS
notifications when incidents are created. When an incident is created,
notifications are sent to the organization’s safety manager based on the
organization’s notification settings. The incident workflow also enqueues
Celery tasks to capture evidence via dashcams and telematics data, as
before.
"""

from __future__ import annotations

import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.db.models import User, Org
from app.db.session import get_db
from app.db.repo.incidents import create_incident, get_incident, list_incidents
from app.db.repo.events import create_event, get_events_by_incident
from app.db.repo.artifacts import get_artifacts_by_incident
from app.db.repo.exports import create_export, get_exports_by_incident
from app.db.repo.users import get_user_org_ids
from app.domain.system_event_types import SystemEventType
from app.tasks.evidence_tasks import collect_evidence
from app.tasks.export_tasks import build_export
from app.services.twilio_notify import build_voice_twiml, send_sms, place_call

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[IncidentListItem])
def list_incidents_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all incidents visible to the current user.

    Incidents are filtered by the organizations the user belongs to. For each
    incident, the counts of captured evidence artifacts are calculated to
    provide quick progress indicators on the dashboard.
    """
    org_ids = get_user_org_ids(db, current_user.id)
    incidents = list_incidents(db, org_ids=org_ids)
    result: List[IncidentListItem] = []
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
                created_at_utc=inc.created_at_utc.isoformat() if inc.created_at_utc else None,
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
    """Create a new incident and begin evidence capture.

    The current user must belong to at least one organization. The incident is
    created in the first organization associated with the user. After the
    incident is created, events are logged to indicate that an incident
    started and evidence lockdown commenced. Evidence capture tasks are
    enqueued via Celery. If the organization has notifications enabled,
    Twilio voice and/or SMS alerts are sent to the configured safety manager.
    """
    # Determine organization: use the first org the user belongs to
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

    # 4. Notify safety manager via Twilio if configured
    if org_id is not None:
        org: Org | None = db.query(Org).filter(Org.id == org_id).first()
        if org:
            notification_payload = {
                "incident_id": str(incident_id),
                "adc_vehicle_id": body.adc_vehicle_id or "unknown vehicle",
                "severity": body.severity or "unspecified",
            }
            # Compose a human-friendly message
            alert_message = (
                f"ADC alert: incident {notification_payload['incident_id']} "
                f"reported for vehicle {notification_payload['adc_vehicle_id']}. "
                f"Severity: {notification_payload['severity']}. Please check the dashboard."
            )
            # Send voice call if enabled
            try:
                if getattr(org, "voice_enabled", False) and org.safety_manager_phone:
                    twiml = build_voice_twiml(alert_message)
                    sid = place_call(org.safety_manager_phone, twiml)
                    logger.info(
                        "Placed Twilio voice call for incident %s to %s (call SID: %s)",
                        incident_id,
                        org.safety_manager_phone,
                        sid,
                    )
            except Exception as twilio_voice_exc:
                logger.warning(
                    "Failed to place Twilio voice call for incident %s: %s",
                    incident_id,
                    twilio_voice_exc,
                )
            # Send SMS if enabled
            try:
                if getattr(org, "sms_enabled", False) and org.safety_manager_phone:
                    sid = send_sms(org.safety_manager_phone, alert_message)
                    logger.info(
                        "Sent Twilio SMS for incident %s to %s (message SID: %s)",
                        incident_id,
                        org.safety_manager_phone,
                        sid,
                    )
            except Exception as twilio_sms_exc:
                logger.warning(
                    "Failed to send Twilio SMS for incident %s: %s",
                    incident_id,
                    twilio_sms_exc,
                )

    # 5. Enqueue Celery evidence-capture workflow
    str_id = str(incident_id)
    window_start = body.window_start or None
    window_end = body.window_end or None
    # Use the orchestrated collect_evidence task to launch both dashcam and telematics
    collect_evidence.delay(str_id, window_start, window_end)

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
    """Return detailed information about a specific incident.

    Includes summary of evidence artifacts, export statuses, and event
    timeline. Access is restricted to users whose organization includes the
    incident.
    """
    org_ids = get_user_org_ids(db, current_user.id)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

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
        created_at_utc=incident.created_at_utc.isoformat() if incident.created_at_utc else None,
        evidence_inventory=[
            ArtifactSummary(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                status=a.status,
                captured_at_utc=(
                    a.capture_window_end_utc.isoformat() if a.capture_window_end_utc else None
                ),
                unavailable_reason=a.unavailable_reason_code,
            )
            for a in artifacts
        ],
        export_status=[
            ExportSummary(
                export_id=e.export_id,
                status=e.status,
                created_at_utc=e.created_at_utc.isoformat() if e.created_at_utc else None,
            )
            for e in exports
        ],
        timeline=[
            EventSummary(
                event_type=ev.event_type,
                occurred_at_utc=ev.occurred_at_utc.isoformat() if ev.occurred_at_utc else "",
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
    """Request an export package for a specific incident.

    Creates a new export record in the database, logs an event, and enqueues
    the export build task. Only users whose organization owns the incident
    may request exports.
    """
    org_ids = get_user_org_ids(db, current_user.id)
    incident = get_incident(db, incident_id, org_ids=org_ids)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

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