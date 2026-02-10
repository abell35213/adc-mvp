"""Driver API routes — driver profile and QR vehicle resolution."""

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import DriverMeResponse, ResolveQrRequest, ResolveQrResponse, VehicleInfo
from app.db.models import Driver, DriverVehicleAssignment, Event, VehicleQrToken
from app.db.session import get_db
from app.domain.system_event_types import SystemEventType

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_current_driver(db: Session = Depends(get_db)):
    """Placeholder dependency — returns the first active driver.

    In production this would extract the authenticated driver identity
    (e.g. from a JWT issued after OTP verification).
    """
    driver = db.query(Driver).filter(Driver.is_active.is_(True)).first()
    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not authenticated",
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
        actor_id="anonymous",
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
