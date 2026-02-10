"""Driver API routes — driver auth, profile, and QR vehicle resolution."""

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverMeResponse,
    ResolveQrRequest,
    ResolveQrResponse,
    VehicleInfo,
)
from app.core.security import decode_access_token
from app.db.models import Driver, DriverVehicleAssignment, Event, VehicleQrToken
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.notify_tasks import notify_safety

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _get_current_driver(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Decode driver JWT and return active driver."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not authenticated",
        )

    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    driver_id = payload.get("sub")
    if driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    try:
        driver_uuid = uuid.UUID(driver_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    driver = (
        db.query(Driver)
        .filter(
            Driver.driver_id == driver_uuid,
            Driver.is_active.is_(True),
        )
        .first()
    )
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not found or inactive",
        )
    return driver




@router.get("/me", response_model=DriverMeResponse)
def driver_me(
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Return the authenticated driver profile and current vehicle (if any)."""
    assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        )
        .first()
    )

    vehicle = None
    if assignment is not None:
        vehicle = VehicleInfo(
            adc_vehicle_id=assignment.adc_vehicle_id,
            display_label=assignment.adc_vehicle_id,
        )

    return DriverMeResponse(
        driver_id=driver.driver_id,
        org_id=driver.org_id,
        phone_e164=driver.phone_e164,
        display_name=driver.display_name,
        vehicle=vehicle,
    )


@router.post("/vehicle/resolve-qr", response_model=ResolveQrResponse)
def resolve_qr(
    body: ResolveQrRequest,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Resolve a QR token to a vehicle. Only active tokens are accepted."""
    token_row = (
        db.query(VehicleQrToken)
        .filter(
            VehicleQrToken.qr_token == body.qr_token,
            VehicleQrToken.status == "active",
        )
        .first()
    )

    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR token not found or inactive",
        )

    # Emit DRIVER_VEHICLE_RESOLVED event — store sha256(token), not raw
    token_hash = hashlib.sha256(body.qr_token.encode()).hexdigest()

    event = Event(
        org_id=token_row.org_id,
        incident_id=None,
        event_type=SystemEventType.DRIVER_VEHICLE_RESOLVED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
        payload={
            "adc_vehicle_id": token_row.adc_vehicle_id,
            "token_sha256": token_hash,
        },
    )
    db.add(event)
    db.commit()

    logger.info(
        "DRIVER_VEHICLE_RESOLVED vehicle=%s token_sha256=%s",
        token_row.adc_vehicle_id,
        token_hash,
    )

    return ResolveQrResponse(
        adc_vehicle_id=token_row.adc_vehicle_id,
        display_label=token_row.adc_vehicle_id,
    )


@router.post("/incidents/initiate", response_model=DriverIncidentInitiateResponse)
def initiate_incident(
    body: DriverIncidentInitiateRequest,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Initiate a driver incident protocol and start evidence capture."""
    adc_vehicle_id = _resolve_vehicle_for_driver(body, driver, db)

    incident = (
        db.query(Incident)
        .filter(
            Incident.org_id == driver.org_id,
            Incident.adc_vehicle_id == adc_vehicle_id,
            Incident.status != "closed",
        )
        .order_by(desc(Incident.created_at_utc))
        .first()
    )
    if incident is None:
        incident = create_incident(
            db,
            status="evidence_capturing",
            adc_vehicle_id=adc_vehicle_id,
            adc_driver_id=str(driver.driver_id),
            org_id=driver.org_id,
        )

    event_payload = {
        "vehicle_strategy": body.vehicle_strategy,
        "adc_vehicle_id": adc_vehicle_id,
        "device_location": body.device_location,
        "device": body.device,
    }
    protocol_event = Event(
        org_id=driver.org_id,
        incident_id=incident.incident_id,
        event_type=SystemEventType.INCIDENT_PROTOCOL_INITIATED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
        payload=event_payload,
    )
    lockdown_event = Event(
        org_id=driver.org_id,
        incident_id=incident.incident_id,
        event_type=SystemEventType.EVIDENCE_LOCKDOWN_STARTED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
    )
    db.add(protocol_event)
    db.add(lockdown_event)
    db.commit()

    str_id = str(incident.incident_id)
    capture_dashcam.delay(str_id, body.window_start, body.window_end)
    capture_telematics_bundle.delay(str_id, body.window_start, body.window_end)
    notify_safety.delay(str_id)

    return DriverIncidentInitiateResponse(
        incident_id=incident.incident_id,
        safety_notified=True,
        capture_started=True,
    )


@router.get("/instructions/active", response_model=DriverInstructionSetResponse)
def get_active_instructions(
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Return the active instruction set for the driver's org."""
    instruction_set = _select_instruction_set(db, driver.org_id)
    if instruction_set is None:
        raise HTTPException(status_code=404, detail="Instruction set not found")

    steps = _instruction_steps(db, instruction_set.instruction_set_id)
    return DriverInstructionSetResponse(
        instruction_set_id=instruction_set.instruction_set_id,
        scope=instruction_set.scope,
        require_ack=instruction_set.require_ack,
        steps=[
            DriverInstructionStepResponse(
                step_id=step.step_id,
                step_order=step.step_order,
                title=step.title,
                body=step.body,
            )
            for step in steps
        ],
    )


@router.post("/instructions/ack", response_model=DriverInstructionAckResponse)
def acknowledge_instructions(
    body: DriverInstructionAckRequest,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Acknowledge the active driver instruction set if required."""
    instruction_set = (
        db.query(DriverInstructionSet)
        .filter(
            DriverInstructionSet.instruction_set_id == body.instruction_set_id,
            DriverInstructionSet.org_id == driver.org_id,
        )
        .first()
    )
    if instruction_set is None:
        raise HTTPException(status_code=404, detail="Instruction set not found")
    if not instruction_set.require_ack:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instruction acknowledgement not required",
        )

    event = Event(
        org_id=driver.org_id,
        incident_id=None,
        event_type=SystemEventType.DRIVER_INSTRUCTION_ACKNOWLEDGED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
        payload={"instruction_set_id": str(instruction_set.instruction_set_id)},
    )
    db.add(event)
    db.commit()

    return DriverInstructionAckResponse(acknowledged=True)


@router.get(
    "/incidents/{incident_id}/status",
    response_model=DriverIncidentStatusResponse,
)
def driver_incident_status(
    incident_id: uuid.UUID,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
):
    """Return status and evidence capture state for an incident."""
    incident = get_incident(db, incident_id, org_ids=[driver.org_id])
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    events = db.query(Event).filter(Event.incident_id == incident_id).all()
    safety_notified = any(
        event.event_type == SystemEventType.INCIDENT_PROTOCOL_INITIATED.value
        for event in events
    )
    evidence_event_types = {
        SystemEventType.EVIDENCE_CAPTURE_REQUESTED.value,
        SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED.value,
        SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED.value,
        SystemEventType.EVIDENCE_CAPTURE_FAILED.value,
        SystemEventType.ARTIFACT_RECORDED.value,
        SystemEventType.ARTIFACT_HASHED.value,
    }
    evidence_events = [
        e
        for e in events
        if e.event_type in evidence_event_types and e.occurred_at_utc is not None
    ]
    last_evidence_update = None
    if evidence_events:
        latest_event = max(evidence_events, key=lambda e: e.occurred_at_utc)
        last_evidence_update = latest_event.occurred_at_utc.isoformat()

    return DriverIncidentStatusResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        safety_notified=safety_notified,
        capture_state=_evidence_capture_state(events, incident.status),
        last_evidence_update_utc=last_evidence_update,
    )
