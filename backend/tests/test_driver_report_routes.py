"""Tests for driver report patch and submit endpoints."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.models import Base, Driver, Event, Incident, Org
from app.db.session import get_db
from app.api.routes.routes_driver_report import router as driver_report_router


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(driver_report_router, prefix="/driver")

    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_driver_and_incident(db_session):
    org = Org(name="Report Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    driver = Driver(
        org_id=org.id,
        phone_e164="+15550001111",
        display_name="Driver Report",
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)

    incident = Incident(
        org_id=org.id,
        adc_driver_id=str(driver.driver_id),
        adc_vehicle_id="veh-1",
        status="open",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    return driver, incident


def _driver_auth_headers(driver_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token({"sub": str(driver_id), "scope": "driver"})
    return {"Authorization": f"Bearer {token}"}


def test_patch_scene_creates_incident_updated_event(
    client, db_session, seeded_driver_and_incident
):
    driver, incident = seeded_driver_and_incident

    response = client.patch(
        f"/driver/incidents/{incident.incident_id}/scene",
        headers=_driver_auth_headers(driver.driver_id),
        json={"scene": {"weather": "rain", "road": "wet"}},
    )

    assert response.status_code == 200
    assert response.json()["updated_sections"] == ["scene"]

    event = (
        db_session.query(Event).filter(Event.incident_id == incident.incident_id).one()
    )
    assert event.event_type == "incident_updated"
    assert event.payload["report_section"] == "scene"
    assert event.payload["report_value"]["weather"] == "rain"


def test_patch_report_rejects_driver_not_owner(
    client, db_session, seeded_driver_and_incident
):
    _driver, incident = seeded_driver_and_incident

    other_driver = Driver(
        org_id=incident.org_id,
        phone_e164="+15550002222",
        display_name="Other Driver",
    )
    db_session.add(other_driver)
    db_session.commit()
    db_session.refresh(other_driver)

    response = client.patch(
        f"/driver/incidents/{incident.incident_id}/report",
        headers=_driver_auth_headers(other_driver.driver_id),
        json={"narrative": "I saw brake lights and slowed down."},
    )

    assert response.status_code == 403


def test_patch_parties_rejects_cross_org_write(
    client, db_session, seeded_driver_and_incident
):
    _driver, incident = seeded_driver_and_incident

    other_org = Org(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    db_session.refresh(other_org)

    cross_org_driver = Driver(
        org_id=other_org.id,
        phone_e164="+15550003333",
        display_name="Cross Org Driver",
    )
    db_session.add(cross_org_driver)
    db_session.commit()
    db_session.refresh(cross_org_driver)

    response = client.patch(
        f"/driver/incidents/{incident.incident_id}/parties",
        headers=_driver_auth_headers(cross_org_driver.driver_id),
        json={"parties": [{"name": "Witness A"}]},
    )

    assert response.status_code == 403


def test_submit_driver_report_writes_submission_event(
    client, db_session, seeded_driver_and_incident
):
    driver, incident = seeded_driver_and_incident

    response = client.post(
        f"/driver/incidents/{incident.incident_id}/submit-driver-report",
        headers=_driver_auth_headers(driver.driver_id),
    )

    assert response.status_code == 200
    assert response.json()["submitted"] is True

    submission_event = (
        db_session.query(Event)
        .filter(
            Event.incident_id == incident.incident_id,
            Event.payload.isnot(None),
        )
        .order_by(Event.created_at_utc.desc())
        .first()
    )
    assert submission_event is not None
    assert submission_event.payload["driver_report_submitted"] is True
