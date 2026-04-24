"""Driver API routes — driver auth, profile, and QR vehicle resolution."""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    DriverActiveIncidentResponse,
    DriverIncidentInitiateRequest,
    DriverIncidentInitiateResponse,
    DriverIncidentStatusResponse,
    DriverInstructionAckRequest,
    DriverInstructionAckResponse,
    DriverTimelineEventWriteRequest,
    DriverTimelineEventWriteResponse,
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
from app.core.deps import get_current_driver
from app.core.security import create_access_token
from app.db.models import (
    Driver,
    DriverInstructionSet,
    DriverInstructionStep as DriverInstructionStepModel,
    DriverVehicleAssignment,
    Event,
    Org,
    OtpChallenge,
    VehicleQrToken,
    Incident,
    OrgVehicleRegistry,
)
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType
from app.services.incident_workflow_service import (
    get_active_incident_for_driver,
    incident_status_summary,
    initiate_driver_incident,
)
from app.security.authn import build_driver_auth_context
from app.security.authz import can_access_driver_incident, require_policy
from app.tasks.evidence_tasks import capture_dashcam, capture_telematics_bundle
from app.tasks.notification_tasks import notify_safety_manager
from app.services.idempotency_service import optional_idempotency_key
from app.services.rate_limit_service import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()
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
    driver: Driver = Depends(get_current_driver),
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
    request: Request,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """Resolve a QR token to a vehicle. Only active tokens are accepted."""
    enforce_rate_limit(
        request,
        bucket_name="driver_qr_resolve",
        subject=str(driver.driver_id),
        max_calls=settings.DRIVER_QR_RESOLVE_RATE_LIMIT,
        window_seconds=settings.DRIVER_QR_RESOLVE_RATE_LIMIT_WINDOW_SECONDS,
        detail="Too many QR resolution attempts. Please retry later.",
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
    vehicle = (
        db.query(OrgVehicleRegistry)
        .filter(
            OrgVehicleRegistry.org_id == token_row.org_id,
            OrgVehicleRegistry.unit_number == token_row.adc_vehicle_id,
        )
        .first()
    )
    if vehicle is not None:
        vehicle.qr_deployment_status = "confirmed"
        vehicle.qr_confirmed_at_utc = datetime.now(timezone.utc)
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


def _get_driver_incident(
    db: Session,
    *,
    incident_id: uuid.UUID,
    driver: Driver,
) -> Incident:
    context = build_driver_auth_context(driver)
    incident = (
        db.query(Incident)
        .filter(
            Incident.incident_id == incident_id,
            Incident.org_id == driver.org_id,
            Incident.adc_driver_id == str(driver.driver_id),
        )
        .first()
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    require_policy(can_access_driver_incident(context, incident))
    return incident


@router.post("/incidents/initiate", response_model=DriverIncidentInitiateResponse)
def initiate_incident(
    body: DriverIncidentInitiateRequest,
    request: Request,
    idempotency=Depends(optional_idempotency_key),
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """Initiate a driver incident protocol and start evidence capture idempotently."""
    enforce_rate_limit(
        request,
        bucket_name="driver_incident_initiate",
        subject=str(driver.driver_id),
        max_calls=15,
        window_seconds=300,
        detail="Too many incident initiation attempts. Please retry later.",
    )
    adc_vehicle_id = _resolve_vehicle_for_driver(body, driver, db)

    initiation = initiate_driver_incident(
        db,
        org_id=driver.org_id,
        driver_id=driver.driver_id,
        adc_vehicle_id=adc_vehicle_id,
        vehicle_strategy=body.vehicle_strategy,
        device_location=body.device_location,
        device=body.device,
        idempotency_key=idempotency.raw_key if idempotency else None,
    )

    if not initiation.protocol_already_started:
        str_id = str(initiation.incident.incident_id)
        capture_dashcam.delay(str_id, body.window_start, body.window_end)
        capture_telematics_bundle.delay(str_id, body.window_start, body.window_end)
        notify_safety_manager.delay(str_id)

    return DriverIncidentInitiateResponse(
        incident_id=initiation.incident.incident_id,
        safety_notified=True,
        capture_started=not initiation.protocol_already_started,
    )


@router.get("/incidents/active", response_model=DriverActiveIncidentResponse)
def get_active_incident(
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """Return the driver's latest active incident."""
    incident = get_active_incident_for_driver(
        db,
        org_id=driver.org_id,
        driver_id=driver.driver_id,
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="No active incident")

    return DriverActiveIncidentResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        adc_vehicle_id=incident.adc_vehicle_id,
        adc_driver_id=incident.adc_driver_id,
        created_at_utc=incident.created_at_utc,
    )


@router.get("/instructions/active", response_model=DriverInstructionSetResponse)
def get_active_instructions(
    driver: Driver = Depends(get_current_driver),
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
    driver: Driver = Depends(get_current_driver),
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

    active_incident = get_active_incident_for_driver(
        db,
        org_id=driver.org_id,
        driver_id=driver.driver_id,
    )
    active_incident_id = (
        active_incident.incident_id if active_incident is not None else None
    )
    acknowledged_at_utc = datetime.now(timezone.utc)

    event = Event(
        org_id=driver.org_id,
        incident_id=active_incident_id,
        event_type=SystemEventType.DRIVER_INSTRUCTION_STEP_ACKNOWLEDGED.value,
        actor_type="driver_app",
        actor_id=str(driver.driver_id),
        occurred_at_utc=acknowledged_at_utc,
        payload={
            "instruction_set_id": str(instruction_set.instruction_set_id),
            "acknowledged_at_utc": acknowledged_at_utc.isoformat(),
        },
    )
    db.add(event)
    db.commit()

    return DriverInstructionAckResponse(acknowledged=True)


@router.post(
    "/incidents/{incident_id}/timeline-events",
    response_model=DriverTimelineEventWriteResponse,
)
def write_driver_timeline_event(
    incident_id: uuid.UUID,
    body: DriverTimelineEventWriteRequest,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """Persist driver app timeline events with actor identity and audit timestamps."""
    incident = _get_driver_incident(
        db,
        incident_id=incident_id,
        driver=driver,
    )

    event_kwargs = {
        "org_id": incident.org_id,
        "incident_id": incident.incident_id,
        "event_type": body.event_name,
        "actor_type": "driver_app",
        "actor_id": str(driver.driver_id),
        "payload": body.payload or {},
    }
    event = Event(
        **event_kwargs,
    )
    db.add(event)
    db.commit()
    return DriverTimelineEventWriteResponse()


@router.get(
    "/incidents/{incident_id}/status",
    response_model=DriverIncidentStatusResponse,
)
def driver_incident_status(
    incident_id: uuid.UUID,
    driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    """Return status and evidence capture state for an incident."""
    incident = _get_driver_incident(
        db,
        incident_id=incident_id,
        driver=driver,
    )

    summary = incident_status_summary(db, incident_id=incident_id)
    events = summary["events"]
    safety_notified = summary["protocol_started_at_utc"] is not None

    return DriverIncidentStatusResponse(
        incident_id=incident.incident_id,
        status=incident.status,
        safety_notified=safety_notified,
        capture_state=_evidence_capture_state(events, incident.status),
        adc_vehicle_id=incident.adc_vehicle_id,
        adc_driver_id=incident.adc_driver_id,
        created_at_utc=incident.created_at_utc,
        protocol_started_at_utc=summary["protocol_started_at_utc"],
        evidence_requested_at_utc=summary["evidence_requested_at_utc"],
        last_evidence_update_utc=summary["last_evidence_update_utc"],
    )
