"""Tests for driver protocol models and defaults."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    Driver,
    DriverInstructionSet,
    DriverInstructionStep,
    DriverVehicleAssignment,
    Org,
    OtpChallenge,
    VehicleQrToken,
)


@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


class TestDriverProtocolDefaults:
    def test_driver_phone_unique(self, db):
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        driver = Driver(
            org_id=org.id,
            phone_e164="+15551234567",
            display_name="A Driver",
        )
        db.add(driver)
        db.commit()

        db.add(
            Driver(
                org_id=org.id,
                phone_e164="+15551234567",
                display_name="B Driver",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()

    def test_otp_challenge_defaults(self, db):
        challenge = OtpChallenge(
            phone_e164="+15550001111",
            otp_code_hash="dummyhash",
            expires_at_utc=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(challenge)
        db.commit()

        assert challenge.status == "pending"
        assert challenge.attempt_count == 0
        assert challenge.created_at_utc is not None

    def test_driver_assignment_source(self, db):
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        driver = Driver(
            org_id=org.id,
            phone_e164="+15559876543",
            display_name="Assigned Driver",
        )
        db.add(driver)
        db.flush()

        assignment = DriverVehicleAssignment(
            org_id=org.id,
            driver_id=driver.driver_id,
            adc_vehicle_id="veh-1",
            source="manual",
        )
        db.add(assignment)
        db.commit()

        assert assignment.source == "manual"

    def test_vehicle_qr_token_index_defined(self):
        table_args = VehicleQrToken.__table_args__
        assert isinstance(table_args, tuple)
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]
        assert "ix_vehicle_qr_tokens_active_vehicle" in index_names

    def test_instruction_step_defaults(self, db):
        org = Org(name="Test Org")
        db.add(org)
        db.flush()

        instruction_set = DriverInstructionSet(org_id=org.id)
        db.add(instruction_set)
        db.commit()

        step = DriverInstructionStep(
            instruction_set_id=instruction_set.instruction_set_id,
            step_order=1,
            title="Step 1",
            body="Do the thing.",
        )
        db.add(step)
        db.commit()

        assert instruction_set.scope == "default"
        assert instruction_set.require_ack is False
        assert step.enabled is True
