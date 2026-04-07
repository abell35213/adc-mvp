from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db.models import Artifact, Base, Export, Incident, Org, User, UserOrg
from app.db.session import get_db
from app.main import app
from app.tasks.export_tasks import build_export


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def orgs(db_session):
    primary = Org(name="Primary Org")
    other = Org(name="Other Org")
    db_session.add_all([primary, other])
    db_session.commit()
    db_session.refresh(primary)
    db_session.refresh(other)
    return primary, other


@pytest.fixture()
def users(db_session, orgs):
    primary, other = orgs
    user_a = User(
        email="section23-a@example.com",
        password_hash=hash_password("secret"),
        role="safety_manager",
    )
    user_b = User(
        email="section23-b@example.com",
        password_hash=hash_password("secret"),
        role="safety_manager",
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    db_session.add_all(
        [
            UserOrg(user_id=user_a.id, org_id=primary.id),
            UserOrg(user_id=user_b.id, org_id=other.id),
        ]
    )
    db_session.commit()
    return user_a, user_b


@pytest.fixture()
def auth_headers(users):
    user_a, user_b = users
    token_a = create_access_token({"sub": str(user_a.id), "role": user_a.role})
    token_b = create_access_token({"sub": str(user_b.id), "role": user_b.role})
    return {
        "primary": {"Authorization": f"Bearer {token_a}"},
        "other": {"Authorization": f"Bearer {token_b}"},
    }


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def incidents(db_session, orgs):
    primary, other = orgs
    first = Incident(org_id=primary.id, status="open", adc_vehicle_id="veh-1")
    second = Incident(org_id=other.id, status="open", adc_vehicle_id="veh-2")
    db_session.add_all([first, second])
    db_session.commit()
    db_session.refresh(first)
    db_session.refresh(second)
    return first, second


@patch("app.api.routes_exports.build_export")
def test_authorization_and_org_isolation(mock_build, client, auth_headers, incidents):
    mock_build.delay = MagicMock()
    own_incident, foreign_incident = incidents

    response = client.post(
        "/exports/",
        headers=auth_headers["primary"],
        json={"incident_id": str(own_incident.incident_id), "export_type": "court_defense"},
    )
    assert response.status_code == 201
    own_export_id = response.json()["export_id"]

    foreign_create = client.post(
        "/exports/",
        headers=auth_headers["primary"],
        json={"incident_id": str(foreign_incident.incident_id), "export_type": "court_defense"},
    )
    assert foreign_create.status_code == 403

    foreign_detail = client.get(f"/exports/{own_export_id}", headers=auth_headers["other"])
    assert foreign_detail.status_code == 403


@patch("app.api.routes_exports.build_export")
def test_lifecycle_requested_to_queued_to_processing_and_ready(
    mock_build,
    client,
    db_session,
    auth_headers,
    incidents,
):
    mock_build.delay = MagicMock(return_value=SimpleNamespace(id="task-1"))
    own_incident, _ = incidents

    created = client.post(
        "/exports/",
        headers=auth_headers["primary"],
        json={"incident_id": str(own_incident.incident_id), "export_type": "court_defense"},
    )
    assert created.status_code == 201
    export_id = created.json()["export_id"]
    assert created.json()["status"] == "queued"

    art = Artifact(
        incident_id=own_incident.incident_id,
        artifact_type="eld_log",
        status="captured",
        s3_key="incidents/a/eld/eld.json",
        sha256="abc",
        byte_size=64,
        capture_window_start_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        capture_window_end_utc=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(art)
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.download.return_value = b"{}"
        s3.put_bytes.return_value = "s3://bucket/key"
        MockS3.return_value = s3

        result = build_export(str(own_incident.incident_id), export_id)
        assert result["status"] == "ready"

    status = client.get(f"/exports/{export_id}/status", headers=auth_headers["primary"])
    assert status.status_code == 200
    assert status.json()["status"] == "ready"
    assert status.json()["progress_stage"] == "ready_for_download"


def test_manifest_and_integrity_outputs(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.add(
        Artifact(
            incident_id=own_incident.incident_id,
            artifact_type="eld_log",
            status="captured",
            s3_key="incidents/a/eld/eld.json",
            sha256="abc",
            byte_size=22,
        )
    )
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.download.return_value = b'{"eld": true}'
        s3.put_bytes.return_value = "s3://bucket/key"
        MockS3.return_value = s3

        build_export(str(own_incident.incident_id), str(export_row.export_id))

    zip_bytes = s3.put_bytes.call_args[0][1]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        package_root = next(name.split("/", 1)[0] for name in names if name.endswith("metadata/export_manifest.json"))
        export_manifest = json.loads(zf.read(f"{package_root}/metadata/export_manifest.json"))
        integrity = json.loads(zf.read(f"{package_root}/metadata/package_integrity.json"))
        checksums = zf.read(f"{package_root}/integrity/checksums.sha256").decode()

    assert f"{package_root}/metadata/export_manifest.json" in names
    assert isinstance(export_manifest.get("file_manifest"), list)
    assert f"{package_root}/metadata/package_integrity.json" in names
    assert isinstance(integrity.get("package_sha256"), str) and len(integrity["package_sha256"]) == 64
    assert integrity.get("file_count", 0) > 0
    assert "01_Incident_Summary.json" in checksums


def test_partial_artifact_soft_fail_behavior(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.add_all(
        [
            Artifact(
                incident_id=own_incident.incident_id,
                artifact_type="eld_log",
                status="captured",
                s3_key="incidents/a/eld/ok.json",
                sha256="ok",
                byte_size=10,
            ),
            Artifact(
                incident_id=own_incident.incident_id,
                artifact_type="photo",
                status="captured",
                s3_key="incidents/a/media/missing.mp4",
                sha256="missing",
                byte_size=10,
            ),
        ]
    )
    db_session.commit()

    def _download(key: str):
        if key.endswith("missing.mp4"):
            raise RuntimeError("not found")
        return b"{}"

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.download.side_effect = _download
        s3.put_bytes.return_value = "s3://bucket/key"
        MockS3.return_value = s3

        result = build_export(str(own_incident.incident_id), str(export_row.export_id))
        assert result["status"] == "ready"
        assert len(result["warnings"]) == 1
        assert len(result["missing_items"]) == 1


def test_hard_fail_path_sets_failed_status(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.export_builder.render_cover_summary_pdf", side_effect=RuntimeError("PDF renderer unavailable")
    ), patch("app.services.vault_s3.VaultS3") as MockS3:
        MockS3.return_value = MagicMock()
        with pytest.raises(RuntimeError, match="PDF renderer unavailable"):
            build_export(str(own_incident.incident_id), str(export_row.export_id))

    failed = db_session.query(Export).filter(Export.export_id == export_row.export_id).first()
    assert failed.status == "failed"
    assert "PDF renderer unavailable" in (failed.error_message or "")


@patch("app.api.routes_exports.build_export")
def test_retry_semantics(mock_build, client, db_session, auth_headers, incidents):
    mock_build.delay = MagicMock(return_value=SimpleNamespace(id="task-2"))
    own_incident, _ = incidents
    failed = Export(
        incident_id=own_incident.incident_id,
        org_id=own_incident.org_id,
        status="failed",
        export_type="court_defense",
    )
    db_session.add(failed)
    db_session.commit()

    response = client.post(
        f"/exports/{failed.export_id}/retry",
        headers=auth_headers["primary"],
        json={"export_type": "court_defense"},
    )
    assert response.status_code == 201

    retried = db_session.query(Export).filter(Export.export_id == uuid.UUID(response.json()["export_id"])).first()
    assert retried.retry_parent_export_id == failed.export_id
    assert retried.status == "queued"


# end-to-end scenarios

def test_e2e_minimal_incident_generates_ready_export(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.put_bytes.return_value = "s3://bucket/key"
        s3.download.return_value = b""
        MockS3.return_value = s3

        result = build_export(str(own_incident.incident_id), str(export_row.export_id))
        assert result["status"] == "ready"


def test_e2e_rich_incident_includes_multiple_artifact_folders(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.add_all(
        [
            Artifact(incident_id=own_incident.incident_id, artifact_type="eld_log", status="captured", s3_key="k/eld.json"),
            Artifact(incident_id=own_incident.incident_id, artifact_type="gps_trail", status="captured", s3_key="k/gps.csv"),
            Artifact(incident_id=own_incident.incident_id, artifact_type="photo", status="captured", s3_key="k/photo.jpg"),
        ]
    )
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.put_bytes.return_value = "s3://bucket/key"
        s3.download.return_value = b"data"
        MockS3.return_value = s3

        build_export(str(own_incident.incident_id), str(export_row.export_id))

    zip_bytes = s3.put_bytes.call_args[0][1]
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert any("/eld/" in name for name in names)
    assert any("/gps/" in name for name in names)
    assert any("/media/" in name for name in names)


def test_e2e_missing_optional_artifacts_still_ready(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.add(
        Artifact(
            incident_id=own_incident.incident_id,
            artifact_type="driver_statement",
            status="unavailable",
            s3_key=None,
        )
    )
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.put_bytes.return_value = "s3://bucket/key"
        MockS3.return_value = s3

        result = build_export(str(own_incident.incident_id), str(export_row.export_id))

    assert result["status"] == "ready"
    assert any(item["kind"] == "driver_statement" for item in result["missing_items"])


def test_e2e_pdf_failure_behavior_sets_failed(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.commit()

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.export_builder.render_cover_summary_pdf", side_effect=RuntimeError("pdf fail")
    ), patch("app.services.vault_s3.VaultS3") as MockS3:
        MockS3.return_value = MagicMock()
        with pytest.raises(RuntimeError, match="pdf fail"):
            build_export(str(own_incident.incident_id), str(export_row.export_id))

    failed = db_session.query(Export).filter(Export.export_id == export_row.export_id).first()
    assert failed.status == "failed"


def test_e2e_single_artifact_retrieval_failure_soft_fails(db_session, incidents):
    own_incident, _ = incidents
    export_row = Export(incident_id=own_incident.incident_id, org_id=own_incident.org_id, status="requested")
    db_session.add(export_row)
    db_session.add_all(
        [
            Artifact(incident_id=own_incident.incident_id, artifact_type="eld_log", status="captured", s3_key="k/ok.json"),
            Artifact(incident_id=own_incident.incident_id, artifact_type="gps_trail", status="captured", s3_key="k/bad.csv"),
        ]
    )
    db_session.commit()

    def _download(key: str):
        if key.endswith("bad.csv"):
            raise RuntimeError("cannot fetch")
        return b"ok"

    with patch("app.tasks.export_tasks._get_db", return_value=db_session), patch(
        "app.services.vault_s3.VaultS3"
    ) as MockS3:
        s3 = MagicMock()
        s3.download.side_effect = _download
        s3.put_bytes.return_value = "s3://bucket/key"
        MockS3.return_value = s3

        result = build_export(str(own_incident.incident_id), str(export_row.export_id))

    assert result["status"] == "ready"
    assert len(result["warnings"]) == 1
