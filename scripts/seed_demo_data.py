#!/usr/bin/env python3
"""Seed deterministic demo entities for incidents/evidence/exports/onboarding.

Creates (or updates) a demo org, an ORG_ADMIN user, a driver, and a vehicle
QR token, then seeds a scenario via app.commercial.demo. Safe to re-run.

Default demo credentials (override via env):
    DEMO_ORG            = "ADC Demo Org"
    DEMO_ADMIN_EMAIL    = "demo-admin@adc.local"
    DEMO_ADMIN_PASSWORD = "DemoAdmin!2345"     # local dev only
    DEMO_DRIVER_PHONE   = "+15551234567"
    DEMO_VEHICLE_ID     = "veh-demo-001"

The demo admin is provisioned as ORG_ADMIN (not SYSTEM_ADMIN) so the seeded
password works against POST /auth/login without MFA enrolment. Do NOT run
this script against staging or production.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.commercial.demo import (
    DEFAULT_SCENARIO_KEY,
    reset_demo_tenant,
    seed_demo_tenant,
    seed_expanded_demo_workspace,
)
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


def _ensure_demo_identity(
    db,
    *,
    org_name: str,
    admin_email: str,
    admin_password: str,
    driver_phone: str,
    vehicle_id: str,
):
    org = db.query(Org).filter_by(name=org_name).first()
    if org is None:
        org = create_org(db, name=org_name)

    user = db.query(User).filter_by(email=admin_email).first()
    if user is None:
        # Demo admin is provisioned as ORG_ADMIN (not SYSTEM_ADMIN) so that
        # password-only login works out of the box. SYSTEM_ADMIN trips the
        # MFA gate in routes_auth._is_mfa_required and the login UI has no
        # MFA field — making the seeded credentials unusable.
        user = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
            role=Role.ORG_ADMIN.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        existing_demo_membership = (
            db.query(UserOrg)
            .filter(UserOrg.user_id == user.id, UserOrg.org_id == org.id)
            .first()
            is not None
        )
        is_stale_demo_seed = (
            user.role == Role.SYSTEM_ADMIN.value or existing_demo_membership
        )

        # Only self-heal known stale demo seeds. Do not mutate unrelated local
        # accounts that happen to share the configured demo admin email.
        if is_stale_demo_seed:
            if user.role != Role.ORG_ADMIN.value:
                user.role = Role.ORG_ADMIN.value
            if not user.is_active:
                user.is_active = True
            # Refresh the password only for known demo-seed accounts so the
            # documented demo credentials work after re-seed.
            user.password_hash = hash_password(admin_password)
            db.commit()
            db.refresh(user)
        elif user.role != Role.ORG_ADMIN.value:
            raise ValueError(
                f"Refusing to modify existing non-demo user for demo admin email: {admin_email}"
            )
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

    token = (
        db.query(VehicleQrToken)
        .filter_by(adc_vehicle_id=vehicle_id, status="active")
        .first()
    )
    if token is None:
        from secrets import token_urlsafe

        token = VehicleQrToken(
            qr_token=token_urlsafe(18),
            org_id=org.id,
            adc_vehicle_id=vehicle_id,
            status="active",
        )
        db.add(token)
        db.commit()
        db.refresh(token)

    return org, user, driver, token


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", default=os.environ.get("DEMO_SCENARIO", DEFAULT_SCENARIO_KEY)
    )
    parser.add_argument("--reset-only", action="store_true")
    args = parser.parse_args()

    org_name = os.environ.get("DEMO_ORG", "ADC Demo Org")
    admin_email = os.environ.get("DEMO_ADMIN_EMAIL", "demo-admin@adc.local")
    admin_password = os.environ.get("DEMO_ADMIN_PASSWORD", "DemoAdmin!2345")
    driver_phone = os.environ.get("DEMO_DRIVER_PHONE", "+15551234567")
    vehicle_id = os.environ.get("DEMO_VEHICLE_ID", "veh-demo-001")

    db = SessionLocal()
    try:
        org, user, driver, token = _ensure_demo_identity(
            db,
            org_name=org_name,
            admin_email=admin_email,
            admin_password=admin_password,
            driver_phone=driver_phone,
            vehicle_id=vehicle_id,
        )

        db.query(DriverVehicleAssignment).filter(
            DriverVehicleAssignment.driver_id == driver.driver_id,
            DriverVehicleAssignment.unassigned_at_utc.is_(None),
        ).delete(synchronize_session=False)
        db.add(
            DriverVehicleAssignment(
                org_id=org.id,
                driver_id=driver.driver_id,
                adc_vehicle_id=vehicle_id,
                source="manual",
            )
        )
        db.commit()

        reset_result = reset_demo_tenant(db, org_id=org.id, actor_id=str(user.id))
        if args.reset_only:
            print(f"reset={reset_result}")
            return

        seeded = seed_demo_tenant(
            db, org_id=org.id, actor=user, scenario_key=args.scenario
        )
        expanded = seed_expanded_demo_workspace(db, org_id=org.id, actor=user)

        print(f"org={org.name} ({org.id})")
        print(f"admin={admin_email}")
        print(f"driver={driver.phone_e164} ({driver.driver_id})")
        print(f"vehicle={vehicle_id}")
        print(f"qr_token={token.qr_token}")
        print(f"reset={reset_result}")
        print(f"seeded={seeded}")
        print(f"expanded={expanded}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
