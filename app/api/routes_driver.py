"""Driver API routes — driver auth, profile, QR resolution and manual evidence uploads.

This module exposes the driver‑facing REST API used by the mobile
application. It is largely derived from the upstream Accident Defense
Command MVP project but has been extended in several ways:

* The ``initiate_incident`` endpoint now triggers the orchestrated
  evidence capture task ``collect_evidence`` instead of individual
  dashcam and telematics tasks. This ensures both capture streams run
  concurrently and the overall success/failure state is recorded.
* A new ``/incidents/{incident_id}/upload`` endpoint allows drivers
  to submit their own photos, videos or notes via the app. Uploaded
  files are stored via ``VaultS3`` and recorded as ``Artifact`` rows
  with type ``manual_upload``. Events are emitted to record the
  arrival of new evidence.

Note that this file intentionally duplicates much of the upstream
driver API for completeness. Only the modifications described above
should diverge from the original implementation.
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverIncidentInitiateRequest,
    DriverIncidentInitiateResponse,
    DriverIncidentStatusResponse,
    DriverInstructionAckRequest,
    DriverInstructionAckResponse,
    DriverInstructionSetResponse,
    DriverInstructionStepResponse,
    DriverMeResponse,
    DriverOtpRequest,
    DriverOtpRequestResponse,
    DriverOtpVerifyRequest,
    DriverOtpVerifyResponse,
    ResolveQrRequest,
    ResolveQrResponse,
    VehicleInfo,
)
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.db.models import (
    Artifact,
    Driver,
    DriverInstructionSet,
    DriverInstructionStep as DriverInstructionStepModel,
    DriverVehicleAssignment,
    Event,
    Incident,
    Org,
    OtpChallenge,
    VehicleQrToken,
)
from app.db.repo.incidents import create_incident, get_incident
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.services.vault_s3 import VaultS3
from app.tasks.evidence_tasks import collect_evidence
from app.tasks.notify_tasks import notify_safety
import asyncio
import json
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# FastAPI router for all driver‑facing endpoints
router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# OTP parameters
OTP_EXPIRATION_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


def _generate_otp_code() -> str:
    """Return a 6‑digit random code with leading zeros."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp_code(code: str) -> str:
    """Hash an OTP code with the application's pepper for secure storage."""
    return hmac.new(
        settings.OTP_HASH_PEPPER.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()


def _get_current_driver(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Driver:
    """Decode driver JWT and return the active driver record.

    Raises ``HTTPException`` with 401 if the token is missing or invalid,
    or if the referenced driver is inactive.
    """
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


def _get_or_create_default_org(db: Session) -> Org:
    """Return the first organization or create a default one if none exist."""
    org = db.query(Org).order_by(Org.name).first()
    if org is None:
        org = Org(name="Default")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def _as_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime from a naive or aware datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("/auth/request-otp", response_model=DriverOtpRequestResponse)
def request_driver_otp(body: DriverOtpRequest, db: Session = Depends(get_db)) -> DriverOtpRequestResponse:
    """Request a one‑time password for driver authentication."""
    phone_e164 = body.phone_e164.strip()
    if not phone_e164:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required",
        )

    now = datetime.now(timezone.utc)
    org = _get_or_create_default_org(db)
    driver = db.query(Driver).filter(Driver.phone_e164 == phone_e164).first()
    if driver is None:
        driver = Driver(
            org_id=org.id,
            phone_e164=phone_e164,
            display_name=phone_e164,
        )
        db.add(driver)
        db.commit()
        db.refresh(driver)

    # Expire any previous pending OTP challenges
    pending_query = db.query(OtpChallenge).filter(
        OtpChallenge.phone_e164 == phone_e164,
        OtpChallenge.status == "pending",
    )
    latest_pending = pending_query.order_by(OtpChallenge.created_at_utc.desc()).first()
    if latest_pending is not None:
        if _as_utc(latest_pending.expires_at_utc) < now:
            latest_pending.status = "expired"
            db.commit()
        elif latest_pending.last_sent_at_utc is not None:
            last_sent = _as_utc(latest_pending.last_sent_at_utc)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                retry_after = max(
                    1,
                    int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="OTP recently sent",
                    headers={"Retry-After": str(retry_after)},
                )

    pending = pending_query.all()
    for challenge in pending:
        challenge.status = "expired"

    otp_code = _generate_otp_code()
    otp = OtpChallenge(
        phone_e164=phone_e164,
        otp_code_hash=_hash_otp_code(otp_code),
        expires_at_utc=now + timedelta(minutes=OTP_EXPIRATION_MINUTES),
        last_sent_at_utc=now,
    )
    db.add(otp)
    db.commit()

    logger.info("OTP challenge requested for driver=%s", phone_e164)
    return DriverOtpRequestResponse()


@router.post("/auth/verify-otp", response_model=DriverOtpVerifyResponse)
def verify_driver_otp(body: DriverOtpVerifyRequest, db: Session = Depends(get_db)) -> DriverOtpVerifyResponse:
    """Verify a one‑time password and issue a JWT on success."""
    phone_e164 = body.phone_e164.strip()
    otp_code = body.otp_code.strip()
    if not phone_e164 or not otp_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number and OTP code are required",
        )

    challenge = (
        db.query(OtpChallenge)
        .filter(
            OtpChallenge.phone_e164 == phone_e164,
            OtpChallenge.status == "pending",
        )
        .order_by(OtpChallenge.created_at_utc.desc())
        .first()
    )
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTP challenge not found",
        )

    now = datetime.now(timezone.utc)
    if _as_utc(challenge.expires_at_utc) < now:
        challenge.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired",
        )

    if challenge.attempt_count >= MAX_OTP_ATTEMPTS:
        challenge.status = "locked"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OTP is locked",
        )

    challenge.attempt_count += 1
    if not hmac.compare_digest(_hash_otp_code(otp_code), challenge.otp_code_hash):
        if challenge.attempt_count >= MAX_OTP_ATTEMPTS:
            challenge.status = "locked"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code",
        )

    challenge.status = "verified"
    db.commit()

    driver = db.query(Driver).filter(Driver.phone_e164 == phone_e164).first()
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found",
        )

    token = create_access_token({"sub": str(driver.driver_id), "role": "driver"})
    return DriverOtpVerifyResponse(access_token=token)


@router.get("/me", response_model=DriverMeResponse)
def driver_me(
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
) -> DriverMeResponse:
    """Return the authenticated driver profile and current vehicle (if any)."""
    assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        )
        .first()
    )

    vehicle: Optional[VehicleInfo] = None
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
) -> ResolveQrResponse:
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


# ── Helper functions for incident and instruction endpoints ──────────


def _resolve_vehicle_for_driver(
    body: DriverIncidentInitiateRequest,
    driver: Driver,
    db: Session,
) -> str:
    """Resolve a vehicle ID from the request body using the chosen strategy."""
    if body.vehicle_strategy == "qr":
        if not body.qr_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="qr_token required for qr strategy",
            )
        token_row = (
            db.query(VehicleQrToken)
            .filter(
                VehicleQrToken.qr_token == body.qr_token,
                VehicleQrToken.status == "active",
                VehicleQrToken.org_id == driver.org_id,
            )
            .first()
        )
        if token_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR token not found or inactive",
            )
        return token_row.adc_vehicle_id
    # Default: last_assigned — find the driver's current vehicle assignment
    assignment = (
        db.query(DriverVehicleAssignment)
        .filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active vehicle assignment for driver",
        )
    return assignment.adc_vehicle_id


_INSTRUCTION_SCOPE_PRIORITY = ["company", "insurer", "default"]


def _select_instruction_set(db: Session, org_id: uuid.UUID) -> Optional[DriverInstructionSet]:
    """Return the highest‑priority instruction set for the organization."""
    for scope in _INSTRUCTION_SCOPE_PRIORITY:
        instruction_set = (
            db.query(DriverInstructionSet)
            .filter(
                DriverInstructionSet.org_id == org_id,
                DriverInstructionSet.scope == scope,
            )
            .first()
        )
        if instruction_set is not None:
            return instruction_set
    return None


def _instruction_steps(db: Session, instruction_set_id: uuid.UUID) -> list:
    """Return ordered instruction steps for the given set."""
    return (
        db.query(DriverInstructionStepModel)
        .filter(
            DriverInstructionStepModel.instruction_set_id == instruction_set_id,
        )
        .order_by(DriverInstructionStepModel.step_order)
        .all()
    )


def _evidence_capture_state(events: list, incident_status: str) -> str:
    """Derive the evidence capture state from incident events."""
    event_types = {e.event_type for e in events}
    if SystemEventType.EVIDENCE_CAPTURE_FAILED.value in event_types:
        return "failed"
    if SystemEventType.EVIDENCE_CAPTURE_SUCCEEDED.value in event_types:
        return "complete"
    if SystemEventType.EVIDENCE_CAPTURE_ATTEMPTED.value in event_types:
        return "in_progress"
    if SystemEventType.EVIDENCE_CAPTURE_REQUESTED.value in event_types:
        return "requested"
    if SystemEventType.EVIDENCE_LOCKDOWN_STARTED.value in event_types:
        return "lockdown"
    if incident_status == "closed":
        return "closed"
    return "pending"


@router.post("/incidents/initiate", response_model=DriverIncidentInitiateResponse)
def initiate_incident(
    body: DriverIncidentInitiateRequest,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
) -> DriverIncidentInitiateResponse:
    """Initiate a driver incident protocol and start evidence capture.

    This endpoint resolves the appropriate vehicle, creates or reuses an
    incident record, emits initiation and lockdown events and then
    enqueues the orchestrated ``collect_evidence`` Celery task along
    with a notification for the safety manager.
    """
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
    # Trigger the orchestrated evidence capture and safety notification
    collect_evidence.delay(str_id, body.window_start, body.window_end)
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
) -> DriverInstructionSetResponse:
    """Return the active instruction set for the driver's organization."""
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
) -> DriverInstructionAckResponse:
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
) -> DriverIncidentStatusResponse:
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
    last_evidence_update: Optional[str] = None
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


@router.post("/incidents/{incident_id}/upload")
async def upload_manual_evidence(
    incident_id: uuid.UUID,
    file: UploadFile = File(...),
    notes: Optional[str] = None,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
) -> dict:
    """Upload manual evidence (photo, video, etc.) for an incident.

    Drivers can supplement automated evidence capture by submitting
    additional files through the driver app. The uploaded file is stored
    using ``VaultS3`` and recorded as an ``Artifact`` of type
    ``manual_upload``. An event is emitted so the dashboard and timeline
    can update immediately.

    Returns a simple JSON object containing the new ``artifact_id`` and
    the S3 key.
    """
    # Validate that the incident exists and belongs to the driver's org
    incident = get_incident(db, incident_id, org_ids=[driver.org_id])
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status == "closed":
        raise HTTPException(status_code=400, detail="Cannot upload evidence to a closed incident")

    # Read the uploaded file into memory
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    # Compute sha256 for integrity
    file_sha256 = hashlib.sha256(content).hexdigest()
    # Determine a key for the object — include a random UUID to avoid collisions
    random_id = uuid.uuid4()
    sanitized_name = file.filename.replace("/", "_") if file.filename else "upload"
    key = f"manual/{incident_id}/{random_id}_{sanitized_name}"
    # Upload to storage
    vault = VaultS3(bucket=settings.S3_BUCKET)
    vault.put_bytes(key, content)
    # Record artifact
    artifact = Artifact(
        org_id=driver.org_id,
        incident_id=incident_id,
        artifact_type="manual_upload",
        status="captured",
        s3_bucket=vault.bucket,
        s3_key=key,
        sha256=file_sha256,
        byte_size=len(content),
    )
    db.add(artifact)
    # Emit event
    event = Event(
        org_id=driver.org_id,
        incident_id=incident_id,
        event_type=SystemEventType.ARTIFACT_RECORDED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
        payload={
            "artifact_type": "manual_upload",
            "artifact_id": str(artifact.artifact_id),
            "filename": sanitized_name,
            "notes": notes or "",
        },
    )
    db.add(event)
    db.commit()
    db.refresh(artifact)
    return {"artifact_id": str(artifact.artifact_id), "s3_key": key}


# ── Real‑time event stream ─────────────────────────────────────────────────

@router.get(
    "/incidents/{incident_id}/events/stream",
    response_class=StreamingResponse,
)
async def stream_incident_events(
    incident_id: uuid.UUID,
    driver: Driver = Depends(_get_current_driver),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Server‑sent events stream of incident events.

    This endpoint provides a simple event stream for the specified
    incident using the Server‑Sent Events (SSE) protocol. Clients can
    open a persistent HTTP connection and receive JSON‑encoded events
    as they are recorded. The stream polls the database every second
    for new events. In a production system you would likely replace
    this with a message broker or dedicated pub/sub mechanism.
    """
    # Ensure the incident belongs to the driver's org
    incident = get_incident(db, incident_id, org_ids=[driver.org_id])
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    last_event_id: Optional[uuid.UUID] = None

    async def event_generator():
        nonlocal last_event_id
        while True:
            # Query for events newer than the last seen ID
            query = db.query(Event).filter(Event.incident_id == incident_id)
            if last_event_id is not None:
                query = query.filter(Event.id != last_event_id)
            events = query.order_by(Event.occurred_at_utc.asc()).all()
            for ev in events:
                last_event_id = ev.id
                data = {
                    "event_id": str(ev.id),
                    "type": ev.event_type,
                    "payload": ev.payload,
                    "timestamp": ev.occurred_at_utc.isoformat() if ev.occurred_at_utc else None,
                }
                yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")