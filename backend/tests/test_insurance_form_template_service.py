"""Tests for the insurance form template editor service (plan test #8)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, InsuranceFormTemplateField, Org
from app.db.repo import insurance_form_templates as repo
from app.services.insurance_form_ocr import DetectedField
from app.services.insurance_form_template_service import (
    FieldSpec,
    TemplateLockedError,
    TemplateNotReadyError,
    add_field,
    clone_for_edit,
    finalize_template,
    ingest_detected_fields,
    remove_field,
    update_field,
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
def template(db_session, org):
    return repo.create_template(
        db_session, org_id=org.id, name="ACORD-1", carrier="Travelers"
    )


class TestVersioning:
    def test_first_template_is_v1(self, template):
        assert template.version == 1
        assert template.status == "draft"

    def test_second_template_with_same_name_increments_version(
        self, db_session, org, template
    ):
        # Same (org_id, name) → next call creates v2.
        v2 = repo.create_template(db_session, org_id=org.id, name=template.name)
        assert v2.version == 2
        assert v2.id != template.id


class TestAddField:
    def test_basic(self, db_session, template):
        field = add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(
                name="DriverName",
                label="Driver Name",
                source_path="driver.display_name",
            ),
        )
        assert field.id is not None
        assert field.template_id == template.id
        assert field.source_path == "driver.display_name"
        assert field.required is False

    def test_invalid_source_path_rejected(self, db_session, template):
        with pytest.raises(Exception):
            add_field(
                db_session,
                template_id=template.id,
                spec=FieldSpec(name="Bad", source_path="9not.valid"),
            )

    def test_invalid_kind_rejected(self, db_session, template):
        with pytest.raises(ValueError):
            add_field(
                db_session,
                template_id=template.id,
                spec=FieldSpec(name="X", kind="bogus"),
            )

    def test_unknown_transform_rejected(self, db_session, template):
        with pytest.raises(ValueError):
            add_field(
                db_session,
                template_id=template.id,
                spec=FieldSpec(
                    name="X",
                    source_path="driver.display_name",
                    transform="surely_not_a_transform",
                ),
            )

    def test_blank_name_rejected(self, db_session, template):
        with pytest.raises(ValueError):
            add_field(
                db_session, template_id=template.id, spec=FieldSpec(name="   ")
            )


class TestUpdateField:
    def test_partial_update(self, db_session, template):
        f = add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        updated = update_field(
            db_session,
            field_id=f.id,
            changes={"transform": "upper", "required": True},
        )
        assert updated.transform == "upper"
        assert updated.required is True
        # Unchanged fields preserved.
        assert updated.source_path == "driver.display_name"

    def test_invalid_change_rejected_atomically(self, db_session, template):
        f = add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        with pytest.raises(Exception):
            update_field(
                db_session,
                field_id=f.id,
                changes={"source_path": "9bad"},
            )
        # Original value still intact.
        db_session.refresh(f)
        assert f.source_path == "driver.display_name"


class TestRemoveField:
    def test_removes(self, db_session, template):
        f = add_field(
            db_session, template_id=template.id, spec=FieldSpec(name="X")
        )
        remove_field(db_session, field_id=f.id)
        assert (
            db_session.query(InsuranceFormTemplateField)
            .filter(InsuranceFormTemplateField.id == f.id)
            .first()
            is None
        )

    def test_remove_nonexistent_is_noop(self, db_session):
        import uuid

        # Must not raise.
        remove_field(db_session, field_id=uuid.uuid4())


class TestIngestDetected:
    def test_creates_fields_from_detection(self, db_session, template):
        created = ingest_detected_fields(
            db_session,
            template_id=template.id,
            detected=[
                DetectedField(name="DriverName", label="Driver Name", kind="text"),
                DetectedField(name="Sig", label="Signature", kind="signature"),
            ],
        )
        assert len(created) == 2
        names = {f.name for f in created}
        assert names == {"DriverName", "Sig"}

    def test_skips_existing_names_on_redetect(self, db_session, template):
        ingest_detected_fields(
            db_session,
            template_id=template.id,
            detected=[DetectedField(name="DriverName", label="Driver Name")],
        )
        # Operator already mapped a source_path on DriverName.
        f = (
            db_session.query(InsuranceFormTemplateField)
            .filter(InsuranceFormTemplateField.name == "DriverName")
            .one()
        )
        f.source_path = "driver.display_name"
        db_session.commit()

        # Re-detect with the same field plus a new one.
        created = ingest_detected_fields(
            db_session,
            template_id=template.id,
            detected=[
                DetectedField(name="DriverName"),
                DetectedField(name="DOTNumber"),
            ],
        )
        assert len(created) == 1
        assert created[0].name == "DOTNumber"
        # The existing operator mapping was preserved.
        db_session.refresh(f)
        assert f.source_path == "driver.display_name"


class TestFinalize:
    def test_happy_path(self, db_session, template):
        add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        finalized = finalize_template(db_session, template_id=template.id)
        assert finalized.status == "finalized"
        assert finalized.finalized_at_utc is not None

    def test_blocks_when_required_missing_source_path(self, db_session, template):
        add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", required=True),  # no source_path
        )
        with pytest.raises(TemplateNotReadyError) as ei:
            finalize_template(db_session, template_id=template.id)
        assert "X" in str(ei.value)

    def test_blocks_when_no_fields(self, db_session, template):
        with pytest.raises(TemplateNotReadyError):
            finalize_template(db_session, template_id=template.id)

    def test_double_finalize_rejected(self, db_session, template):
        add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        finalize_template(db_session, template_id=template.id)
        with pytest.raises(TemplateLockedError):
            finalize_template(db_session, template_id=template.id)


class TestEditingFinalizedTemplateBlocked:
    def test_add_field_blocked(self, db_session, template):
        add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        finalize_template(db_session, template_id=template.id)
        with pytest.raises(TemplateLockedError):
            add_field(
                db_session,
                template_id=template.id,
                spec=FieldSpec(name="Y", source_path="driver.phone_e164"),
            )

    def test_update_field_blocked(self, db_session, template):
        f = add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        finalize_template(db_session, template_id=template.id)
        with pytest.raises(TemplateLockedError):
            update_field(db_session, field_id=f.id, changes={"required": True})


class TestCloneForEdit:
    def test_clones_with_new_version_and_field_copy(self, db_session, template):
        add_field(
            db_session,
            template_id=template.id,
            spec=FieldSpec(name="X", source_path="driver.display_name"),
        )
        finalize_template(db_session, template_id=template.id)

        new = clone_for_edit(db_session, template_id=template.id)
        assert new.id != template.id
        assert new.version == template.version + 1
        assert new.status == "draft"
        # Field copied across.
        new_fields = repo.list_template_fields(db_session, new.id)
        assert len(new_fields) == 1
        assert new_fields[0].source_path == "driver.display_name"
