"""Tests for the storage backend factory and the synchronous filesystem download.

These cover the controlled-pilot wiring that resolves the active vault from
``settings.STORAGE_BACKEND`` and streams export ZIP bytes directly through the
download endpoint when the filesystem backend is active.
"""

import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.models import Base, Export, Incident, Org, User, UserOrg
from app.db.session import get_db
from app.main import app
from app.services import vault_fs, vault_s3
from app.services.storage import (
    FILESYSTEM_BACKEND,
    S3_BACKEND,
    get_vault,
    is_filesystem_backend,
    normalize_storage_backend,
)


# ── Factory unit tests ──────────────────────────────────────────────


class TestNormalizeStorageBackend:
    @pytest.mark.parametrize("value", ["filesystem", "fs", "file", "local", "LOCAL", " Fs "])
    def test_filesystem_aliases(self, value):
        assert normalize_storage_backend(value) == FILESYSTEM_BACKEND

    @pytest.mark.parametrize("value", ["s3", "aws", "aws_s3", "S3", " s3 "])
    def test_s3_aliases(self, value):
        assert normalize_storage_backend(value) == S3_BACKEND

    @pytest.mark.parametrize("value", ["", None, "gcs", "azure", "unknown"])
    def test_unsupported_raises(self, value):
        with pytest.raises(ValueError):
            normalize_storage_backend(value)


class TestGetVault:
    def test_filesystem_backend_returns_filesystem_vault(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "filesystem")
        monkeypatch.setattr(settings, "VAULT_ROOT", str(tmp_path))

        assert is_filesystem_backend(settings) is True
        vault = get_vault(settings)
        assert isinstance(vault, vault_fs.VaultFilesystem)
        assert str(vault.root) == str(tmp_path)

    def test_fs_alias_routes_to_filesystem_vault(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "fs")
        monkeypatch.setattr(settings, "VAULT_ROOT", str(tmp_path))

        assert is_filesystem_backend(settings) is True
        assert isinstance(get_vault(settings), vault_fs.VaultFilesystem)

    def test_s3_backend_returns_s3_vault(self, monkeypatch):
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")

        assert is_filesystem_backend(settings) is False
        assert isinstance(get_vault(settings), vault_s3.VaultS3)

    def test_get_vault_honors_vault_s3_patch(self, monkeypatch):
        """Existing tests patch app.services.vault_s3.VaultS3; the factory must respect it."""
        monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")

        sentinel = object()
        with patch("app.services.vault_s3.VaultS3", return_value=sentinel) as mock_s3:
            assert get_vault(settings) is sentinel
            mock_s3.assert_called_once()


# ── Filesystem export build + synchronous download round-trip ───────


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_org(db_session):
    org = Org(name="Filesystem Vault Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def test_user(db_session, test_org):
    user = User(
        email="fs-vault@example.com",
        password_hash=hash_password("testpass"),
        role="safety_manager",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(UserOrg(user_id=user.id, org_id=test_org.id))
    db_session.commit()
    return user


@pytest.fixture()
def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def filesystem_backend(monkeypatch, tmp_path):
    """Activate the filesystem vault rooted at a temp dir for the whole test."""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "filesystem")
    monkeypatch.setattr(settings, "VAULT_ROOT", str(tmp_path))
    return tmp_path


class TestFilesystemExportDownloadRoundTrip:
    def test_build_export_persists_zip_to_filesystem_vault(
        self, filesystem_backend, db_session, test_org
    ):
        inc = Incident(
            status="evidence_capturing",
            adc_vehicle_id="v1",
            org_id=test_org.id,
        )
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            incident_id=inc.incident_id,
            org_id=test_org.id,
            status="requested",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        from app.tasks.export_tasks import build_export

        with patch("app.tasks.export_tasks._get_db", return_value=db_session):
            result = build_export(str(inc.incident_id), str(exp.export_id))

        assert result["status"] == "ready"

        updated = (
            db_session.query(Export)
            .filter(Export.export_id == exp.export_id)
            .first()
        )
        assert updated.status == "ready"
        assert updated.s3_key

        # The ZIP was written to the local filesystem vault and is a valid archive.
        stored = vault_fs.VaultFilesystem(root=str(filesystem_backend)).get_bytes(
            updated.s3_key
        )
        with zipfile.ZipFile(io.BytesIO(stored)) as zf:
            assert zf.namelist()

    def test_download_streams_zip_bytes_for_filesystem_backend(
        self, filesystem_backend, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        # Persist a real ZIP package into the vault under the export's key.
        package_key = (
            f"orgs/{test_org.id}/incidents/{inc.incident_id}"
            f"/artifacts/{exp.export_id}.zip"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("readme/00_README.txt", "pilot package")
        package_bytes = buffer.getvalue()
        vault_fs.VaultFilesystem(root=str(filesystem_backend)).put_bytes(
            package_key, package_bytes
        )

        exp.s3_key = package_key
        db_session.commit()

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert f"{exp.export_id}.zip" in resp.headers["content-disposition"]
        assert resp.content == package_bytes
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert "readme/00_README.txt" in zf.namelist()

    def test_download_records_stream_delivery_event(
        self, filesystem_backend, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        package_key = (
            f"orgs/{test_org.id}/incidents/{inc.incident_id}/artifacts/pkg.zip"
        )
        vault_fs.VaultFilesystem(root=str(filesystem_backend)).put_bytes(
            package_key, b"PK\x03\x04 not-a-real-zip-but-bytes"
        )

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_key=package_key,
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 200

        from app.db.models import Event

        events = (
            db_session.query(Event).filter(Event.incident_id == inc.incident_id).all()
        )
        download_event = next(
            e for e in events if e.event_type == "export_downloaded"
        )
        assert download_event.payload["delivery"] == "stream"
        assert download_event.payload["status"] == "ready"
        assert download_event.payload["export_id"] == str(exp.export_id)

    def test_download_missing_key_returns_409_for_filesystem_backend(
        self, filesystem_backend, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_key=None,
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "EXPORT_DELAYED"

    def test_download_missing_file_returns_502_for_filesystem_backend(
        self, filesystem_backend, client, db_session, test_org, auth_headers
    ):
        inc = Incident(status="open", org_id=test_org.id)
        db_session.add(inc)
        db_session.commit()
        db_session.refresh(inc)

        # Key points at a path that was never written to the vault.
        missing_key = (
            f"orgs/{test_org.id}/incidents/{inc.incident_id}/artifacts/missing.zip"
        )
        exp = Export(
            org_id=test_org.id,
            incident_id=inc.incident_id,
            status="ready",
            s3_key=missing_key,
        )
        db_session.add(exp)
        db_session.commit()
        db_session.refresh(exp)

        resp = client.get(f"/exports/{exp.export_id}/download", headers=auth_headers)
        assert resp.status_code == 502
        assert resp.json()["detail"]["code"] == "THIRD_PARTY_DEGRADED"
