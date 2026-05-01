"""Tests for the insurance form fill orchestration (plan test #10)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Artifact, Base, Incident, InsuranceFormFilling, Org
from app.db.repo import insurance_form_templates as templates_repo
from app.services.crash_packet_query import CrashPacketRow
from app.services.insurance_form_fill_service import (
    fill_form_for_incident,
)
from app.services.insurance_form_template_service import (
    FieldSpec,
    add_field,
    finalize_template,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def org(db_session):
    o = Org(name="Acme")
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def incident(db_session, org):
    i = Incident(status="accident_occurred", org_id=org.id)
    db_session.add(i)
    db_session.commit()
    db_session.refresh(i)
    return i


@pytest.fixture()
def fake_row():
    """A canonical row with both populated and absent sections.

    Used by every fill test via the ``mock_fetch`` fixture below; that's
    enough surface area to cover the resolver's happy-path, missing-key,
    and indexed-list paths without spinning up the real query layer.
    """
    return CrashPacketRow(
        incident_json={
            "incident_id": "inc-1",
            "adc_vehicle_id": "T-100",
            "severity": "serious",
        },
        driver_json={"display_name": "pat smith", "phone_e164": "+15551234567"},
        driver_history_json=[],
        vehicle_json={"unit_number": "T-100", "vin": "1HGBH41JXMN109186"},
        trailer_json={"unit_number": "TR-9", "vin": "TRAILVIN0001"},
        maintenance_json=[
            {"vendor": "ShopA", "summary": "brake check", "mileage": 100000}
        ],
        eld_logs_json=[],
        samsara_clip_links_json=[],
        related_event_count=2,
    )


@pytest.fixture()
def mock_fetch(monkeypatch, fake_row):
    """Patch ``fetch_crash_packet_row`` at its import site in the fill service."""
    monkeypatch.setattr(
        "app.services.insurance_form_fill_service.fetch_crash_packet_row",
        lambda _db, *, incident_id: fake_row,
    )
    return fake_row


@pytest.fixture()
def template(db_session, org):
    """A finalized template with three fields covering the common resolution paths."""
    t = templates_repo.create_template(
        db_session, org_id=org.id, name="ACORD-1", carrier="Travelers"
    )
    add_field(
        db_session,
        template_id=t.id,
        spec=FieldSpec(
            name="DriverName",
            label="Driver Name",
            source_path="driver.display_name",
            transform="upper",
            required=True,
        ),
    )
    add_field(
        db_session,
        template_id=t.id,
        spec=FieldSpec(
            name="VehicleVIN",
            label="Vehicle VIN",
            source_path="vehicle.vin",
            required=True,
        ),
    )
    add_field(
        db_session,
        template_id=t.id,
        spec=FieldSpec(
            name="LastShop",
            label="Last shop",
            source_path="maintenance[0].vendor",
        ),
    )
    return finalize_template(db_session, template_id=t.id)


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


class TestFillHappyPath:
    def test_creates_filling_and_artifact(
        self, db_session, incident, template, mock_fetch
    ):
        result = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )
        assert result.created is True
        assert result.filling.status == "filled"
        assert result.filling.template_version == template.version
        assert result.filling.missing_required_fields == []
        assert result.filling.output_artifact_id is not None
        assert result.pdf_bytes is not None and len(result.pdf_bytes) > 0

        # Artifact row was created with sha256 + byte_size populated.
        artifact = (
            db_session.query(Artifact)
            .filter(Artifact.artifact_id == result.filling.output_artifact_id)
            .one()
        )
        assert artifact.artifact_type == "insurance_form_filled"
        assert artifact.status == "captured"
        assert artifact.sha256
        assert artifact.byte_size == len(result.pdf_bytes)
        assert artifact.org_id == template.org_id
        assert artifact.incident_id == incident.incident_id

    def test_payload_records_resolved_values(
        self, db_session, incident, template, mock_fetch
    ):
        result = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )
        by_name = {f["name"]: f for f in result.filling.payload_json["fields"]}
        # ``upper`` transform applied.
        assert by_name["DriverName"]["value"] == "PAT SMITH"
        assert by_name["VehicleVIN"]["value"] == "1HGBH41JXMN109186"
        assert by_name["LastShop"]["value"] == "ShopA"
        assert by_name["DriverName"]["source_path"] == "driver.display_name"


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_resubmit_returns_existing_filling_no_new_artifact(
        self, db_session, incident, template, mock_fetch
    ):
        first = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )
        artifact_count_after_first = db_session.query(Artifact).count()

        second = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )
        assert second.created is False
        assert second.filling.id == first.filling.id
        assert second.pdf_bytes is None
        # No additional Artifact row was created.
        assert db_session.query(Artifact).count() == artifact_count_after_first
        # And only one filling row total.
        assert (
            db_session.query(InsuranceFormFilling)
            .filter(InsuranceFormFilling.incident_id == incident.incident_id)
            .count()
            == 1
        )

    def test_changed_canonical_data_creates_new_filling(
        self, db_session, incident, template, monkeypatch, fake_row
    ):
        # First fill with the original row.
        monkeypatch.setattr(
            "app.services.insurance_form_fill_service.fetch_crash_packet_row",
            lambda _db, *, incident_id: fake_row,
        )
        fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )

        # Now the canonical row's vehicle VIN changes (e.g. corrected ELD).
        new_row = CrashPacketRow(
            incident_json=fake_row.incident_json,
            driver_json=fake_row.driver_json,
            driver_history_json=fake_row.driver_history_json,
            vehicle_json={"unit_number": "T-100", "vin": "CORRECTEDVIN12345"},
            trailer_json=fake_row.trailer_json,
            maintenance_json=fake_row.maintenance_json,
            eld_logs_json=fake_row.eld_logs_json,
            samsara_clip_links_json=fake_row.samsara_clip_links_json,
            related_event_count=fake_row.related_event_count,
        )
        monkeypatch.setattr(
            "app.services.insurance_form_fill_service.fetch_crash_packet_row",
            lambda _db, *, incident_id: new_row,
        )
        second = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
        )
        assert second.created is True
        assert (
            db_session.query(InsuranceFormFilling)
            .filter(InsuranceFormFilling.incident_id == incident.incident_id)
            .count()
            == 2
        )


# ─────────────────────────────────────────────────────────────────────────────
# Missing-required-fields short-circuit
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingRequired:
    def test_records_failed_filling_without_artifact(
        self, db_session, incident, org, monkeypatch
    ):
        # Build a row where ``vehicle`` is None so the required ``VehicleVIN``
        # field cannot be resolved.
        sparse_row = CrashPacketRow(
            incident_json={"incident_id": "inc-x"},
            driver_json={"display_name": "p"},
            vehicle_json=None,
        )
        monkeypatch.setattr(
            "app.services.insurance_form_fill_service.fetch_crash_packet_row",
            lambda _db, *, incident_id: sparse_row,
        )

        t = templates_repo.create_template(
            db_session, org_id=org.id, name="ACORD-2"
        )
        add_field(
            db_session,
            template_id=t.id,
            spec=FieldSpec(
                name="DriverName",
                source_path="driver.display_name",
                required=True,
            ),
        )
        add_field(
            db_session,
            template_id=t.id,
            spec=FieldSpec(
                name="VehicleVIN", source_path="vehicle.vin", required=True
            ),
        )
        finalize_template(db_session, template_id=t.id)

        result = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=t.id,
        )
        assert result.filling.status == "failed"
        assert result.filling.missing_required_fields == ["VehicleVIN"]
        assert result.filling.output_artifact_id is None
        # No Artifact row created.
        assert db_session.query(Artifact).count() == 0
        assert "VehicleVIN" in (result.filling.error_message or "")


# ─────────────────────────────────────────────────────────────────────────────
# Pre-condition errors
# ─────────────────────────────────────────────────────────────────────────────


class TestPreconditions:
    def test_unknown_template_raises(self, db_session, incident, mock_fetch):
        import uuid

        with pytest.raises(LookupError):
            fill_form_for_incident(
                db_session,
                incident_id=incident.incident_id,
                template_id=uuid.uuid4(),
            )

    def test_draft_template_rejected(self, db_session, incident, org, mock_fetch):
        t = templates_repo.create_template(db_session, org_id=org.id, name="X")
        add_field(
            db_session,
            template_id=t.id,
            spec=FieldSpec(name="A", source_path="driver.display_name"),
        )
        # Note: NOT finalized.
        with pytest.raises(ValueError):
            fill_form_for_incident(
                db_session,
                incident_id=incident.incident_id,
                template_id=t.id,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Pluggable S3 writer
# ─────────────────────────────────────────────────────────────────────────────


class TestS3Writer:
    def test_custom_writer_invoked_and_metadata_persisted(
        self, db_session, incident, template, mock_fetch
    ):
        captured: dict = {}

        def writer(*, content, content_type, suggested_key):
            captured["content_type"] = content_type
            captured["key"] = suggested_key
            captured["size"] = len(content)
            return ("my-bucket", "uploaded/" + suggested_key)

        result = fill_form_for_incident(
            db_session,
            incident_id=incident.incident_id,
            template_id=template.id,
            s3_writer=writer,
        )
        artifact = (
            db_session.query(Artifact)
            .filter(Artifact.artifact_id == result.filling.output_artifact_id)
            .one()
        )
        assert artifact.s3_bucket == "my-bucket"
        assert artifact.s3_key.startswith("uploaded/insurance_forms/")
        assert captured["content_type"] == "application/pdf"
        assert captured["size"] == artifact.byte_size
