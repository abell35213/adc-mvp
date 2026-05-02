"""Tests for the Phase 4 ``crash_with_full_packet`` demo scenario.

Verifies that:

* The new scenario is exposed in :data:`SCENARIO_CATALOG` and
  ``list_scenarios`` returns it.
* Seeding produces all three phases' records: Phase 1 notification +
  delivery row, Phase 2 trailer + maintenance, Phase 3 finalized
  template + filled artifact.
* The fill is sourced from the canonical ``CrashPacketRow`` (the
  ``DriverName`` field's resolved value comes from the seeded Driver row,
  not the placeholder text id originally written onto the incident).
* Reset cleans up the new tables so a re-launch of the same scenario
  doesn't duplicate or leak rows.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commercial.demo import (
    SCENARIO_CATALOG,
    launch_scenario,
    list_scenarios,
    reset_demo_tenant,
    seed_demo_tenant,
)
from app.core.security import hash_password
from app.db.models import (
    Artifact,
    Base,
    CrashPacketDelivery,
    Driver,
    Incident,
    InsuranceFormFilling,
    InsuranceFormTemplate,
    MaintenanceRecord,
    Org,
    OrgNotificationRecipient,
    Trailer,
    User,
    UserOrg,
)
from app.security.permissions import Role


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
    o = Org(name="Demo Phase4 Org")
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def actor(db_session, org):
    u = User(
        email="demo-admin@example.com",
        password_hash=hash_password("x"),
        role=Role.ORG_ADMIN.value,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    db_session.add(UserOrg(user_id=u.id, org_id=org.id))
    db_session.commit()
    return u


# ─────────────────────────────────────────────────────────────────────────────
# Catalog surface
# ─────────────────────────────────────────────────────────────────────────────


class TestCatalogSurface:
    def test_scenario_is_in_catalog(self):
        keys = [s.scenario_key for s in SCENARIO_CATALOG]
        assert "crash_with_full_packet" in keys

    def test_list_scenarios_includes_it(self, db_session, org):
        rows = list_scenarios(db_session, org_id=org.id)
        keys = [r["scenario_id"] for r in rows]
        assert "crash_with_full_packet" in keys
        # Not yet seeded → is_active False.
        entry = next(r for r in rows if r["scenario_id"] == "crash_with_full_packet")
        assert entry["is_active"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Seeding produces all three phases' records
# ─────────────────────────────────────────────────────────────────────────────


class TestSeedingProducesAllPhases:
    def test_returns_ids_for_every_new_record(self, db_session, org, actor):
        result = seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        assert result["scenario_id"] == "crash_with_full_packet"
        # Phase-specific ids are surfaced for verify-demo to assert on.
        for key in (
            "incident_id",
            "driver_id",
            "trailer_id",
            "recipient_id",
            "crash_packet_delivery_id",
            "insurance_form_template_id",
            "insurance_form_filling_id",
            "insurance_form_artifact_id",
        ):
            assert key in result and result[key], (
                f"seed result missing/empty {key}: {result}"
            )

    def test_incident_status_is_accident_occurred(self, db_session, org, actor):
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        incident = (
            db_session.query(Incident)
            .filter(Incident.org_id == org.id)
            .one()
        )
        assert incident.status == "accident_occurred"
        assert incident.adc_trailer_id is not None
        assert incident.adc_trailer_id.startswith("trl-demo-")

    def test_phase1_recipient_and_delivery_seeded(self, db_session, org, actor):
        result = seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        recipients = (
            db_session.query(OrgNotificationRecipient)
            .filter(OrgNotificationRecipient.org_id == org.id)
            .all()
        )
        assert len(recipients) == 1
        assert recipients[0].email == "claims-demo@adc.local"
        assert recipients[0].active is True

        deliveries = (
            db_session.query(CrashPacketDelivery)
            .filter(CrashPacketDelivery.org_id == org.id)
            .all()
        )
        assert len(deliveries) == 1
        assert deliveries[0].status == "sent"
        assert str(deliveries[0].id) == result["crash_packet_delivery_id"]

    def test_phase2_trailer_and_maintenance_seeded(self, db_session, org, actor):
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        trailers = (
            db_session.query(Trailer).filter(Trailer.org_id == org.id).all()
        )
        assert len(trailers) == 1
        assert trailers[0].vin == "TRDEMO00000000001"

        maint = (
            db_session.query(MaintenanceRecord)
            .filter(MaintenanceRecord.org_id == org.id)
            .all()
        )
        assert len(maint) == 3
        # At least one record per asset kind.
        kinds = {m.asset_kind for m in maint}
        assert kinds == {"tractor", "trailer"}

    def test_phase3_template_finalized_and_filled(self, db_session, org, actor):
        result = seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        template = (
            db_session.query(InsuranceFormTemplate)
            .filter(InsuranceFormTemplate.org_id == org.id)
            .one()
        )
        assert template.status == "finalized"
        assert template.name == "ACORD-DEMO"
        assert str(template.id) == result["insurance_form_template_id"]

        filling = (
            db_session.query(InsuranceFormFilling)
            .filter(InsuranceFormFilling.template_id == template.id)
            .one()
        )
        assert filling.status == "filled"
        assert filling.missing_required_fields == []
        assert filling.output_artifact_id is not None

        artifact = (
            db_session.query(Artifact)
            .filter(Artifact.artifact_id == filling.output_artifact_id)
            .one()
        )
        assert artifact.artifact_type == "insurance_form_filled"
        assert artifact.status == "captured"
        assert artifact.byte_size and artifact.byte_size > 0
        assert artifact.sha256

    def test_filled_payload_resolved_from_canonical_row(
        self, db_session, org, actor
    ):
        """The DriverName field's value should reflect the actual seeded Driver
        (with the ``upper`` transform applied), not the placeholder text id
        originally stored on ``incident.adc_driver_id``."""
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        filling = db_session.query(InsuranceFormFilling).one()
        by_name = {
            f["name"]: f for f in filling.payload_json["fields"]
        }
        assert by_name["DriverName"]["value"] == "PAT DEMO-DRIVER"
        # Trailer VIN resolved through Phase 2 trailer table.
        assert by_name["TrailerVIN"]["value"] == "TRDEMO00000000001"
        # Most-recent maintenance vendor resolved through Phase 2 list
        # (ordering: newest first within the canonical 1-year window).
        assert by_name["LastMaintVendor"]["value"] == "ShopAlpha"
        assert by_name["VehicleUnit"]["value"] == "veh-demo-crashpacket-001"


# ─────────────────────────────────────────────────────────────────────────────
# Reset cleans up the new tables
# ─────────────────────────────────────────────────────────────────────────────


class TestResetCleansAllPhases:
    def test_reset_then_re_seed_does_not_duplicate(self, db_session, org, actor):
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        reset_demo_tenant(db_session, org_id=org.id, actor_id=str(actor.id))

        # Everything the scenario writes should now be gone.
        assert db_session.query(Incident).count() == 0
        assert db_session.query(Trailer).count() == 0
        assert db_session.query(MaintenanceRecord).count() == 0
        assert db_session.query(OrgNotificationRecipient).count() == 0
        assert db_session.query(CrashPacketDelivery).count() == 0
        assert db_session.query(InsuranceFormFilling).count() == 0
        assert db_session.query(InsuranceFormTemplate).count() == 0
        assert (
            db_session.query(Driver)
            .filter(Driver.display_name == "Pat Demo-Driver")
            .count()
            == 0
        )

        # Seeding again should succeed (no unique-constraint collisions).
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        assert db_session.query(Incident).count() == 1
        assert db_session.query(InsuranceFormFilling).count() == 1


class TestLaunchScenarioOrchestration:
    def test_launch_scenario_resets_then_seeds(self, db_session, org, actor):
        # First seed via the helper.
        seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="crash_with_full_packet",
        )
        first_incident_id = (
            db_session.query(Incident.incident_id)
            .filter(Incident.org_id == org.id)
            .scalar()
        )

        # launch_scenario internally resets + re-seeds.
        result = launch_scenario(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_id="crash_with_full_packet",
        )

        # New incident, plus the resulting payload still surfaces all the
        # Phase 4 ids.
        assert result["incident_id"] != str(first_incident_id)
        assert "insurance_form_filling_id" in result
        # Exactly one of each across the org.
        assert db_session.query(Incident).count() == 1
        assert db_session.query(InsuranceFormTemplate).count() == 1
        assert db_session.query(InsuranceFormFilling).count() == 1
        assert db_session.query(CrashPacketDelivery).count() == 1


class TestNonImpactToOtherScenarios:
    """Phase 4 changes must not regress the original two scenarios."""

    def test_minor_collision_still_seeds(self, db_session, org, actor):
        result = seed_demo_tenant(
            db_session,
            org_id=org.id,
            actor=actor,
            scenario_key="driver_minor_collision",
        )
        assert result["scenario_id"] == "driver_minor_collision"
        # The Phase 4 supplemental dict keys must NOT leak into other scenarios.
        for k in (
            "driver_id",
            "trailer_id",
            "recipient_id",
            "crash_packet_delivery_id",
            "insurance_form_template_id",
        ):
            assert k not in result
        # And no Phase 1/2/3 rows should have been written.
        assert db_session.query(Trailer).count() == 0
        assert db_session.query(InsuranceFormTemplate).count() == 0
        assert db_session.query(CrashPacketDelivery).count() == 0


# ─────────────────────────────────────────────────────────────────────────────
# scripts/verify_demo.py smoke test
# ─────────────────────────────────────────────────────────────────────────────


class TestVerifyDemoScript:
    """The Makefile target ``verify-demo`` shells out to this script; CI
    relies on it returning 0 for the happy path. Run it in-process to
    catch import or wiring regressions without spawning a subprocess."""

    def test_run_returns_zero(self):
        import importlib.util
        from pathlib import Path

        script_path = (
            Path(__file__).resolve().parent.parent.parent
            / "scripts"
            / "verify_demo.py"
        )
        spec = importlib.util.spec_from_file_location(
            "_verify_demo_under_test", script_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.run() == 0
