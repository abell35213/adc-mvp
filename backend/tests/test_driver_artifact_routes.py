"""Tests for driver artifact upload/list endpoints."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.routes_driver_artifacts import router as driver_artifacts_router
from app.core.security import create_access_token
from app.db.models import Artifact, Base, Driver, Incident, Org
from app.db.session import get_db


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
    app.include_router(driver_artifacts_router, prefix="/driver")

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
    org = Org(name="Artifacts Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    driver = Driver(
        org_id=org.id,
        phone_e164="+15559990000",
        display_name="Driver Artifacts",
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)

    incident = Incident(
        org_id=org.id,
        adc_driver_id=str(driver.driver_id),
        adc_vehicle_id="veh-art",
        status="open",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    return driver, incident


def _driver_auth_headers(driver_id: uuid.UUID) -> dict[str, str]:
    token = create_access_token({"sub": str(driver_id), "scope": "driver"})
    return {"Authorization": f"Bearer {token}"}


def test_issue_upload_url_creates_pending_artifact(
    client,
    db_session,
    seeded_driver_and_incident,
):
    driver, incident = seeded_driver_and_incident

    s3_client = MagicMock()
    s3_client.generate_presigned_url.return_value = "https://upload.example.com/put"

    with patch("app.services.artifact_upload_service.boto3.client", return_value=s3_client):
        response = client.post(
            f"/driver/incidents/{incident.incident_id}/artifacts/upload-url",
            headers=_driver_auth_headers(driver.driver_id),
            json={
                "artifact_type": "driver_document",
                "content_type": "application/pdf",
                "file_name": "insurance-card.pdf",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_url"] == "https://upload.example.com/put"
    assert payload["expires_in_seconds"] == 300

    artifact = db_session.query(Artifact).filter(Artifact.incident_id == incident.incident_id).one()
    assert artifact.status == "pending"
    assert artifact.artifact_type == "driver_document"
    assert artifact.capture_window_end_utc is not None
    assert artifact.uploaded_at_utc is None


def test_issue_upload_url_rejects_disallowed_content_type(client, seeded_driver_and_incident):
    driver, incident = seeded_driver_and_incident

    response = client.post(
        f"/driver/incidents/{incident.incident_id}/artifacts/upload-url",
        headers=_driver_auth_headers(driver.driver_id),
        json={
            "artifact_type": "driver_video",
            "content_type": "application/pdf",
            "file_name": "clip.pdf",
        },
    )

    assert response.status_code == 422


def test_complete_upload_marks_artifact_captured(client, db_session, seeded_driver_and_incident):
    driver, incident = seeded_driver_and_incident

    artifact = Artifact(
        org_id=incident.org_id,
        incident_id=incident.incident_id,
        artifact_type="driver_photo",
        status="pending",
        s3_bucket="bucket",
        s3_key="org/key",
    )
    db_session.add(artifact)
    db_session.commit()
    db_session.refresh(artifact)

    response = client.post(
        f"/driver/incidents/{incident.incident_id}/artifacts/complete",
        headers=_driver_auth_headers(driver.driver_id),
        json={
            "artifact_id": str(artifact.artifact_id),
            "byte_size": 2048,
            "sha256": "a" * 64,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "captured"

    db_session.refresh(artifact)
    assert artifact.status == "captured"
    assert artifact.byte_size == 2048
    assert artifact.capture_window_end_utc is None
    assert artifact.uploaded_at_utc is not None


def test_list_artifacts_enforces_driver_ownership(client, db_session, seeded_driver_and_incident):
    _driver, incident = seeded_driver_and_incident

    other_org = Org(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    db_session.refresh(other_org)

    other_driver = Driver(
        org_id=other_org.id,
        phone_e164="+15559990001",
        display_name="Other Driver",
    )
    db_session.add(other_driver)
    db_session.commit()
    db_session.refresh(other_driver)

    response = client.get(
        f"/driver/incidents/{incident.incident_id}/artifacts",
        headers=_driver_auth_headers(other_driver.driver_id),
    )

    assert response.status_code == 404


def test_complete_rejects_cross_incident_artifact_id(
    client,
    db_session,
    seeded_driver_and_incident,
):
    driver, incident = seeded_driver_and_incident
    other_incident = Incident(
        org_id=incident.org_id,
        adc_driver_id=str(driver.driver_id),
        adc_vehicle_id="veh-other",
        status="open",
    )
    db_session.add(other_incident)
    db_session.commit()
    db_session.refresh(other_incident)

    foreign_artifact = Artifact(
        org_id=incident.org_id,
        incident_id=other_incident.incident_id,
        artifact_type="driver_photo",
        status="pending",
    )
    db_session.add(foreign_artifact)
    db_session.commit()
    db_session.refresh(foreign_artifact)

    response = client.post(
        f"/driver/incidents/{incident.incident_id}/artifacts/complete",
        headers=_driver_auth_headers(driver.driver_id),
        json={
            "artifact_id": str(foreign_artifact.artifact_id),
            "byte_size": 2048,
            "sha256": "b" * 64,
        },
    )

    assert response.status_code == 404
