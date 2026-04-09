"""Production-hardening regression coverage for core security and resilience controls."""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_exports import _resolve_authorized_export
from app.core.security import create_access_token, decode_access_token, hash_password
from app.db.models import Base, Export, Incident, Org, User, UserOrg
from app.db.session import get_db
from app.main import app
from app.services import rate_limit_service
from app.services.rate_limit_service import enforce_rate_limit
from app.tasks import celery_app as celery_module
from app.tasks.export_tasks import _assemble_zip


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _user_headers(user_id: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token({"sub": str(user_id), "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_authz_boundary_blocks_incident_creation_without_org_membership(client, db_session):
    outsider = User(
        email="outsider@example.com",
        password_hash=hash_password("secret"),
        role="safety_manager",
    )
    db_session.add(outsider)
    db_session.commit()

    response = client.post(
        "/incidents/",
        json={
            "severity": "minor",
            "adc_vehicle_id": "veh-1",
            "samsara_vehicle_id": "sam-1",
            "adc_driver_id": "driver-1",
        },
        headers=_user_headers(outsider.id, outsider.role),
    )

    assert response.status_code == 403


def test_org_isolation_excludes_foreign_exports_from_listing(client, db_session):
    member_org = Org(name="Member Org")
    foreign_org = Org(name="Foreign Org")
    caller = User(
        email="member@example.com",
        password_hash=hash_password("secret"),
        role="safety_manager",
    )
    db_session.add_all([member_org, foreign_org, caller])
    db_session.commit()

    db_session.add(UserOrg(user_id=caller.id, org_id=member_org.id))
    own_incident = Incident(status="open", org_id=member_org.id)
    foreign_incident = Incident(status="open", org_id=foreign_org.id)
    db_session.add_all([own_incident, foreign_incident])
    db_session.commit()

    own_export = Export(incident_id=own_incident.incident_id, org_id=member_org.id, status="ready")
    foreign_export = Export(incident_id=foreign_incident.incident_id, org_id=foreign_org.id, status="ready")
    db_session.add_all([own_export, foreign_export])
    db_session.commit()

    response = client.get("/exports/", headers=_user_headers(caller.id, caller.role))
    rows = response.json()

    assert response.status_code == 200
    assert {row["export_id"] for row in rows} == {str(own_export.export_id)}


def test_export_permission_check_rejects_cross_org_download(db_session):
    member_org = Org(name="Member")
    foreign_org = Org(name="Foreign")
    caller = User(
        email="manager@example.com",
        password_hash=hash_password("secret"),
        role="safety_manager",
    )
    db_session.add_all([member_org, foreign_org, caller])
    db_session.commit()

    db_session.add(UserOrg(user_id=caller.id, org_id=member_org.id))
    foreign_incident = Incident(status="open", org_id=foreign_org.id)
    db_session.add(foreign_incident)
    db_session.commit()

    foreign_export = Export(incident_id=foreign_incident.incident_id, org_id=foreign_org.id, status="ready")
    db_session.add(foreign_export)
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        _resolve_authorized_export(db_session, foreign_export.export_id, [member_org.id])

    assert getattr(exc_info.value, "status_code", None) == 403


def test_session_expiry_rejects_expired_access_token():
    expired = create_access_token({"sub": "user-1"}, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(expired) is None


def test_rate_limit_enforcement_returns_429_when_threshold_hit(monkeypatch):
    app_for_test = FastAPI()

    @app_for_test.get("/limited")
    def limited_endpoint(request: Request):
        enforce_rate_limit(
            request,
            bucket_name="test-limiter",
            subject="subject-1",
            max_calls=3,
            window_seconds=60,
            detail="Too many requests",
        )
        return {"ok": True}

    monkeypatch.setattr(rate_limit_service, "_get_redis_client", lambda: object())
    monkeypatch.setattr(rate_limit_service, "_run_rate_limit_script", lambda *args, **kwargs: (0, 9))

    with TestClient(app_for_test) as tc:
        response = tc.get("/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "9"


def test_secret_leakage_controls_hash_rate_limit_subject():
    key = rate_limit_service._redis_key(
        bucket_name="export_request",
        subject="driver@example.com",
        window_seconds=60,
    )

    assert "driver@example.com" not in key
    assert len(key.split(":")[2]) == 64


def test_worker_recovery_controls_route_terminal_failures_to_dead_letter(monkeypatch):
    send_task = MagicMock()
    monkeypatch.setattr(celery_module.celery_app, "send_task", send_task)

    sender = SimpleNamespace(name="app.tasks.export_tasks.build_export", max_retries=1, request=SimpleNamespace(retries=1))
    celery_module.route_terminal_failures_to_dead_letter(
        sender=sender,
        task_id="task-123",
        exception=RuntimeError("boom"),
        args=("incident-1", "export-1"),
        kwargs={"attempt_context": {"attempt_number": 2}},
    )

    send_task.assert_called_once()
    _, kwargs = send_task.call_args
    assert kwargs["queue"] == "dead_letter"


def test_storage_outage_simulation_keeps_export_zip_generation_resilient():
    ctx = SimpleNamespace(
        readme_content="Readme",
        inventory_csv_bytes=b"h1,h2\n",
        coc_csv_bytes=b"h1,h2\n",
        appendix_csv_bytes=b"h1,h2\n",
        exportable_artifacts=[
            (SimpleNamespace(artifact_type="dashcam", s3_key="orgs/org-1/incidents/inc-1/artifacts/a.mp4"), "a.mp4")
        ],
        s3=SimpleNamespace(download=MagicMock(side_effect=OSError("simulated storage outage"))),
        warnings=[],
        missing_items=[],
        zip_bytes=b"",
    )

    _assemble_zip(ctx)

    assert ctx.warnings and ctx.warnings[0]["kind"] == "artifact_missing_from_s3"
    assert ctx.missing_items and ctx.missing_items[0]["kind"] == "dashcam"

    with zipfile.ZipFile(io.BytesIO(ctx.zip_bytes), "r") as archive:
        names = set(archive.namelist())

    assert "ADC_Court_Package/00_README.txt" in names
    assert "ADC_Court_Package/integrity_appendix.csv" in names
