"""Repository layer for vehicles.

This module encapsulates common queries and persistence operations
for the ``Vehicle`` model. Vehicles belong to organizations, and most
operations take a list of ``org_ids`` to ensure callers only access
their own data.
"""

from __future__ import annotations

import uuid as _uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Vehicle


def list_vehicles(
    db: Session,
    org_ids: List[_uuid.UUID] | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Vehicle]:
    """Return all vehicles visible to the given org(s).

    If ``org_ids`` is None, all vehicles are returned. Otherwise the
    query is filtered to vehicles whose ``org_id`` is in the provided
    list. Vehicles that have been deactivated (``is_active`` is False)
    are still returned; callers may choose to filter them out in the
    service layer.
    """
    query = db.query(Vehicle)
    if org_ids is not None:
        query = query.filter(Vehicle.org_id.in_(org_ids))
    return query.order_by(Vehicle.created_at_utc.desc()).offset(skip).limit(limit).all()


def get_vehicle(
    db: Session,
    vehicle_id: _uuid.UUID,
    org_ids: List[_uuid.UUID] | None = None,
) -> Optional[Vehicle]:
    """Retrieve a single vehicle by its UUID.

    If ``org_ids`` is provided, the vehicle must belong to one of the
    allowed organizations to be returned.
    """
    query = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id)
    if org_ids is not None:
        query = query.filter(Vehicle.org_id.in_(org_ids))
    return query.first()


def get_vehicle_by_adc_id(
    db: Session,
    adc_vehicle_id: str,
    org_ids: List[_uuid.UUID] | None = None,
) -> Optional[Vehicle]:
    """Retrieve a vehicle by its human‑friendly ADC vehicle identifier."""
    query = db.query(Vehicle).filter(Vehicle.adc_vehicle_id == adc_vehicle_id)
    if org_ids is not None:
        query = query.filter(Vehicle.org_id.in_(org_ids))
    return query.first()


def create_vehicle(
    db: Session,
    org_id: _uuid.UUID,
    adc_vehicle_id: str,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
    vin: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Vehicle:
    """Persist a new vehicle and return the created instance."""
    vehicle = Vehicle(
        org_id=org_id,
        adc_vehicle_id=adc_vehicle_id,
        make=make,
        model=model,
        year=year,
        vin=vin,
        display_name=display_name,
        is_active=True,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(
    db: Session,
    vehicle_id: _uuid.UUID,
    *,
    adc_vehicle_id: Optional[str] = None,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
    vin: Optional[str] = None,
    display_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Vehicle]:
    """Update fields on an existing vehicle.

    Only fields provided as non‑None arguments are updated. Returns the
    updated vehicle or ``None`` if the vehicle does not exist.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).with_for_update().first()
    if vehicle is None:
        return None

    if adc_vehicle_id is not None:
        vehicle.adc_vehicle_id = adc_vehicle_id
    if make is not None:
        vehicle.make = make
    if model is not None:
        vehicle.model = model
    if year is not None:
        vehicle.year = year
    if vin is not None:
        vehicle.vin = vin
    if display_name is not None:
        vehicle.display_name = display_name
    if is_active is not None:
        vehicle.is_active = is_active

    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(
    db: Session,
    vehicle_id: _uuid.UUID,
) -> bool:
    """Delete a vehicle record entirely.

    In most cases callers should prefer setting ``is_active`` to False
    instead of hard deletion. Returns ``True`` if the record existed and
    was removed, else ``False``.
    """
    vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
    if vehicle is None:
        return False
    db.delete(vehicle)
    db.commit()
    return True