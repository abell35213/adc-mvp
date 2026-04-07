#!/usr/bin/env python3
"""Seed minimal demo entities for the driver -> safety -> export story."""

import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import hash_password
from app.db.models import (
    Driver,
    DriverVehicleAssignment,
    Org,
    User,
    UserOrg,
    VehicleQrToken,
)
from app.db.repo.users import create_org
from app.db.session import SessionLocal
from app.security.permissions import Role


def main():
    org_name = os.environ.get("DEMO_ORG", "ADC Demo Org")
    admin_email = os.environ.get("DEMO_ADMIN_EMAIL", "demo-admin@adc.local")
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-admin")
    driver_phone = os.environ.get("DEMO_DRIVER_PHONE", "+15551234567")
    vehicle_id = os.environ.get("DEMO_VEHICLE_ID", "veh-demo-001")

    db = SessionLocal()
    try:
        org = db.query(Org).filter_by(name=org_name).first()
        if org is None:
            org = create_org(db, name=org_name)

        user = db.query(User).filter_by(email=admin_email).first()
        if user is None:
            user = User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                role=Role.ORG_ADMIN.value,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        if (
            db.query(UserOrg)
            .filter(UserOrg.user_id == user.id, UserOrg.org_id == org.id)
            .first()
            is None
        ):
            db.add(UserOrg(user_id=user.id, org_id=org.id))
            db.commit()

        driver = db.query(Driver).filter_by(phone_e164=driver_phone).first()
        if driver is None:
            driver = Driver(
                org_id=org.id,
                phone_e164=driver_phone,
                display_name="Demo Driver",
            )
            db.add(driver)
            db.commit()
            db.refresh(driver)

        token = db.query(VehicleQrToken).filter_by(adc_vehicle_id=vehicle_id, status="active").first()
        if token is None:
            token = VehicleQrToken(
                qr_token=secrets.token_urlsafe(18),
                org_id=org.id,
                adc_vehicle_id=vehicle_id,
                status="active",
            )
            db.add(token)
            db.commit()
            db.refresh(token)

        db.query(DriverVehicleAssignment).filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        ).update(
            {"unassigned_at_utc": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        db.add(
            DriverVehicleAssignment(
                org_id=org.id,
                driver_id=driver.driver_id,
                adc_vehicle_id=vehicle_id,
                source="manual",
            )
        )
        db.commit()

        print(f"org={org.name} ({org.id})")
        print(f"admin={admin_email}")
        print(f"driver={driver.phone_e164} ({driver.driver_id})")
        print(f"vehicle={vehicle_id}")
        print(f"qr_token={token.qr_token}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
