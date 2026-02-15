"""Driver API routes — driver auth, profile, and QR vehicle resolution."""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.notify_tasks import notify_safety

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)
OTP_EXPIRATION_MINUTES = 10
MAX_OTP_ATTEMPTS = 5


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp_code(code: str) -> str:
    return hmac.new(
        settings.OTP_HASH_PEPPER.encode(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()


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


def _get_or_create_default_org(db: Session) -> Org:
    org = db.query(Org).order_by(Org.name).first()
    if org is None:
        org = Org(name="Default")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("/legacy/auth/request-otp", response_model=DriverOtpRequestResponse)
def request_driver_otp(body: DriverOtpRequest, db: Session = Depends(get_db)):
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


@router.post("/legacy/auth/verify-otp", response_model=DriverOtpVerifyResponse)
def verify_driver_otp(body: DriverOtpVerifyRequest, db: Session = Depends(get_db)):
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


# ── Helper functions for incident / instruction endpoints ──────────


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


def _select_instruction_set(
    db: Session,
    org_id: uuid.UUID,
) -> DriverInstructionSet | None:
    """Return the highest-priority instruction set for the org."""
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


def _instruction_steps(
    db: Session,
    instruction_set_id: uuid.UUID,
) -> list:
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
