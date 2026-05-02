"""Demo tenant orchestration helpers and scenario launch workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.audit.emitter import emit_audit_event
from app.db.models import (
    Artifact,
    AuditEvent,
    CrashPacketDelivery,
    DemoScenario,
    Driver,
    DriverVehicleAssignment,
    Event,
    Export,
    Incident,
    InsuranceFormFilling,
    InsuranceFormTemplate,
    MaintenanceRecord,
    Org,
    OrgExportValidationRun,
    OrgNotificationRecipient,
    OrgOnboardingStepCompletion,
    OrgTestIncidentRun,
    Trailer,
    User,
)
from app.onboarding.service import create_export_validation_run, create_test_incident_run, set_step_completion_override
from app.services.insurance_form_template_service import (
    FieldSpec,
    add_field,
    finalize_template,
)
from app.db.repo import insurance_form_templates as insurance_templates_repo

DEMO_FEATURES: tuple[str, ...] = (
    "demo.workspace",
    "demo.incident_seed",
)


@dataclass(frozen=True)
class DemoScenarioDefinition:
    scenario_key: str
    name: str
    description: str


SCENARIO_CATALOG: tuple[DemoScenarioDefinition, ...] = (
    DemoScenarioDefinition(
        scenario_key="driver_minor_collision",
        name="Driver minor collision",
        description="Seeds a ready-for-review incident with captured evidence and a completed export.",
    ),
    DemoScenarioDefinition(
        scenario_key="escalated_follow_up",
        name="Escalated follow-up",
        description="Seeds an escalated incident with incomplete evidence and onboarding blockers.",
    ),
    DemoScenarioDefinition(
        scenario_key="crash_with_full_packet",
        name="Crash with full insurance packet",
        description=(
            "End-to-end crash workflow: trailer + maintenance history (Phase 2), "
            "accident_occurred status with a sent crash-packet delivery (Phase 1), "
            "and a finalized insurance form template filled into a PDF artifact (Phase 3)."
        ),
    ),
)

DEFAULT_SCENARIO_KEY = SCENARIO_CATALOG[0].scenario_key
DEMO_ACTOR_TYPE = "system"
SEED_SOURCE = "demo_orchestrator"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_incident_values(scenario_key: str) -> dict[str, object]:
    if scenario_key == "escalated_follow_up":
        return {
            "status": "open",
            "case_status": "escalated",
            "severity": "serious",
            "readiness_state": "partial",
            "completeness_percent": 64,
            "completeness_status": "needs_follow_up",
            "vehicle_id": "veh-demo-escalated-001",
            "driver_id": "drv-demo-escalated-001",
        }

    if scenario_key == "crash_with_full_packet":
        # Phase 1+2+3 end-to-end: incident is post-collision so the Phase 1
        # crash-packet hook would fire in production. The seeder mocks that
        # by writing a CrashPacketDelivery row directly so the demo viewer
        # sees a "sent" packet without needing Celery + SES.
        return {
            "status": "accident_occurred",
            "case_status": "ready_for_export",
            "severity": "serious",
            "readiness_state": "complete",
            "completeness_percent": 100,
            "completeness_status": "ready",
            "vehicle_id": "veh-demo-crashpacket-001",
            "driver_id": "drv-demo-crashpacket-001",
            "trailer_id": "trl-demo-crashpacket-001",
        }

    return {
        "status": "evidence_capturing",
        "case_status": "ready_for_export",
        "severity": "minor",
        "readiness_state": "complete",
        "completeness_percent": 100,
        "completeness_status": "ready",
        "vehicle_id": "veh-demo-collision-001",
        "driver_id": "drv-demo-collision-001",
    }


def list_scenarios(db: Session, *, org_id: uuid.UUID) -> list[dict[str, object]]:
    """List curated scenarios and org launch state."""
    rows = (
        db.query(DemoScenario)
        .filter(DemoScenario.org_id == org_id)
        .order_by(DemoScenario.updated_at_utc.desc())
        .all()
    )
    by_key = {row.scenario_key: row for row in rows}

    scenarios: list[dict[str, object]] = []
    for definition in SCENARIO_CATALOG:
        row = by_key.get(definition.scenario_key)
        scenarios.append(
            {
                "scenario_id": definition.scenario_key,
                "name": definition.name,
                "description": definition.description,
                "is_active": bool(row.is_active) if row is not None else False,
                "seed_batch_id": row.seed_batch_id if row is not None else None,
                "seeded_at_utc": row.updated_at_utc if row is not None else None,
            }
        )
    return scenarios


def reset_demo_tenant(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor_id: str,
    include_audit_record: bool = True,
) -> dict[str, int]:
    """Delete deterministic demo scenario records for an org."""
    incident_ids = [
        row.incident_id
        for row in db.query(Incident.incident_id)
        .filter(
            Incident.org_id == org_id,
            Incident.adc_vehicle_id.like("veh-demo-%"),
        )
        .all()
    ]

    deleted_counts = {
        "incidents": len(incident_ids),
        "artifacts": 0,
        "exports": 0,
        "events": 0,
        "audit_events": 0,
    }

    if incident_ids:
        deleted_counts["audit_events"] += (
            db.query(AuditEvent)
            .filter(
                AuditEvent.org_id == org_id,
                AuditEvent.incident_id.in_(incident_ids),
            )
            .delete(synchronize_session=False)
        )
        deleted_counts["events"] += (
            db.query(Event)
            .filter(Event.org_id == org_id, Event.incident_id.in_(incident_ids))
            .delete(synchronize_session=False)
        )
        # Phase 1: crash-packet deliveries (incident_id FK).
        db.query(CrashPacketDelivery).filter(
            CrashPacketDelivery.incident_id.in_(incident_ids)
        ).delete(synchronize_session=False)
        # Phase 3: fillings reference both incidents (CASCADE) and artifacts
        # (SET NULL) and templates (RESTRICT). Delete fillings explicitly so
        # the template wipe below isn't blocked by RESTRICT.
        db.query(InsuranceFormFilling).filter(
            InsuranceFormFilling.incident_id.in_(incident_ids)
        ).delete(synchronize_session=False)
        deleted_counts["artifacts"] = (
            db.query(Artifact)
            .filter(Artifact.org_id == org_id, Artifact.incident_id.in_(incident_ids))
            .delete(synchronize_session=False)
        )
        export_ids = [
            row.export_id
            for row in db.query(Export.export_id)
            .filter(Export.org_id == org_id, Export.incident_id.in_(incident_ids))
            .all()
        ]
        if export_ids:
            deleted_counts["audit_events"] += (
                db.query(AuditEvent)
                .filter(
                    AuditEvent.org_id == org_id,
                    AuditEvent.export_id.in_(export_ids),
                )
                .delete(synchronize_session=False)
            )
        deleted_counts["exports"] = (
            db.query(Export)
            .filter(Export.org_id == org_id, Export.incident_id.in_(incident_ids))
            .delete(synchronize_session=False)
        )
        db.query(Incident).filter(Incident.incident_id.in_(incident_ids)).delete(
            synchronize_session=False
        )

    # Phase 2: trailers + maintenance records seeded by the crash_with_full_packet
    # scenario. Filter narrowly so non-demo data in the same org is untouched.
    db.query(Trailer).filter(
        Trailer.org_id == org_id, Trailer.adc_trailer_id.like("trl-demo-%")
    ).delete(synchronize_session=False)
    db.query(MaintenanceRecord).filter(
        MaintenanceRecord.org_id == org_id,
        MaintenanceRecord.asset_id.like("veh-demo-%")
        | MaintenanceRecord.asset_id.like("trl-demo-%"),
    ).delete(synchronize_session=False)
    # Driver + assignment seeded by the same scenario.
    demo_driver_ids = [
        row.driver_id
        for row in db.query(Driver.driver_id)
        .filter(
            Driver.org_id == org_id,
            Driver.display_name == "Pat Demo-Driver",
        )
        .all()
    ]
    if demo_driver_ids:
        db.query(DriverVehicleAssignment).filter(
            DriverVehicleAssignment.org_id == org_id,
            DriverVehicleAssignment.driver_id.in_(demo_driver_ids),
        ).delete(synchronize_session=False)
        db.query(Driver).filter(
            Driver.driver_id.in_(demo_driver_ids)
        ).delete(synchronize_session=False)
    # Phase 1: notification recipient seeded by the scenario.
    db.query(OrgNotificationRecipient).filter(
        OrgNotificationRecipient.org_id == org_id,
        OrgNotificationRecipient.email == "claims-demo@adc.local",
    ).delete(synchronize_session=False)
    # Phase 3: demo template (fillings already wiped above, so the
    # RESTRICT FK doesn't block this).
    db.query(InsuranceFormTemplate).filter(
        InsuranceFormTemplate.org_id == org_id,
        InsuranceFormTemplate.name.like("ACORD-DEMO%"),
    ).delete(synchronize_session=False)

    db.query(OrgTestIncidentRun).filter(OrgTestIncidentRun.org_id == org_id).delete(
        synchronize_session=False
    )
    db.query(OrgExportValidationRun).filter(OrgExportValidationRun.org_id == org_id).delete(
        synchronize_session=False
    )
    db.query(OrgOnboardingStepCompletion).filter(
        OrgOnboardingStepCompletion.org_id == org_id,
        OrgOnboardingStepCompletion.completion_source == SEED_SOURCE,
    ).delete(synchronize_session=False)
    db.query(DemoScenario).filter(DemoScenario.org_id == org_id).delete(
        synchronize_session=False
    )

    db.commit()

    if include_audit_record:
        emit_audit_event(
            db,
            org_id=org_id,
            actor_type=DEMO_ACTOR_TYPE,
            actor_id=actor_id,
            action="demo.tenant.reset",
            event_type="demo_tenant_reset",
            outcome="success",
            metadata={"deleted": deleted_counts},
        )
    return deleted_counts


def seed_demo_tenant(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    scenario_key: str = DEFAULT_SCENARIO_KEY,
) -> dict[str, object]:
    """Seed deterministic incident/evidence/export/onboarding demo records."""
    matching = [item for item in SCENARIO_CATALOG if item.scenario_key == scenario_key]
    if not matching:
        raise ValueError("unknown_scenario")
    definition = matching[0]
    now_utc = _utc_now()
    state = _seed_incident_values(scenario_key)

    incident = Incident(
        org_id=org_id,
        status=str(state["status"]),
        case_status=str(state["case_status"]),
        severity=str(state["severity"]),
        adc_vehicle_id=str(state["vehicle_id"]),
        samsara_vehicle_id=f"sm-{state['vehicle_id']}",
        adc_driver_id=str(state["driver_id"]),
        adc_trailer_id=str(state["trailer_id"]) if state.get("trailer_id") else None,
        readiness_state=str(state["readiness_state"]),
        completeness_percent=int(state["completeness_percent"]),
        completeness_status=str(state["completeness_status"]),
        owner_user_id=actor.id,
        owner_assigned_by_user_id=actor.id,
        owner_assigned_at_utc=now_utc - timedelta(minutes=20),
        last_activity_at_utc=now_utc - timedelta(minutes=2),
    )
    db.add(incident)
    db.flush()

    evidence_status = "pending" if scenario_key == "escalated_follow_up" else "captured"
    for artifact_type in ("dashcam_forward", "dashcam_cabin", "eld_logs"):
        db.add(
            Artifact(
                org_id=org_id,
                incident_id=incident.incident_id,
                artifact_type=artifact_type,
                status=evidence_status,
                capture_window_start_utc=now_utc - timedelta(minutes=30),
                capture_window_end_utc=now_utc - timedelta(minutes=5),
                uploaded_at_utc=now_utc - timedelta(minutes=3)
                if evidence_status == "captured"
                else None,
            )
        )

    export_status = "ready" if scenario_key != "escalated_follow_up" else "failed"
    export = Export(
        org_id=org_id,
        incident_id=incident.incident_id,
        export_type="insurer_packet",
        profile_id="insurer_packet_v1",
        requested_by_user_id=actor.id,
        status=export_status,
        progress_stage="ready_for_download" if export_status == "ready" else "assembling_documents",
        artifact_count=3,
        timeline_event_count=4,
        requested_at_utc=now_utc - timedelta(minutes=2),
        completed_at_utc=now_utc if export_status == "ready" else None,
    )
    db.add(export)

    db.add(
        Event(
            org_id=org_id,
            incident_id=incident.incident_id,
            event_type="demo_incident_seeded",
            actor_type=DEMO_ACTOR_TYPE,
            actor_id=str(actor.id),
            occurred_at_utc=now_utc,
            payload={"scenario_key": scenario_key},
        )
    )

    run = create_test_incident_run(
        db,
        org_id=org_id,
        actor_user_id=actor.id,
        incident_id=incident.incident_id,
        findings=["Seeded via demo orchestrator"],
    )
    db.flush()

    create_export_validation_run(
        db,
        org_id=org_id,
        actor_user_id=actor.id,
        status="completed" if export_status == "ready" else "failed",
        checks={"required_sections_present": export_status == "ready"},
        details={"scenario_key": scenario_key},
        warnings=[],
        missing_items=[] if export_status == "ready" else [{"item": "eld_logs"}],
        incident_id=incident.incident_id,
        export_id=export.export_id,
    )

    set_step_completion_override(
        db,
        org_id=org_id,
        step_key="testIncidentCompleted",
        is_completed=export_status == "ready",
        actor_user_id=actor.id,
        source=SEED_SOURCE,
    )

    seed_batch_id = f"seed-{now_utc.strftime('%Y%m%d%H%M%S')}"
    db.add(
        DemoScenario(
            org_id=org_id,
            scenario_key=definition.scenario_key,
            name=definition.name,
            description=definition.description,
            seeded_by=actor.email,
            seed_batch_id=seed_batch_id,
            seed_metadata_json={"incident_id": str(incident.incident_id), "test_run_id": str(run.run_id)},
        )
    )

    # Phase 4: optional cross-phase supplement for the crash_with_full_packet
    # scenario. Adds Phase 2 trailer + maintenance, Phase 1 notification +
    # delivery rows, and a Phase 3 finalized template that is filled inline
    # against this incident so a viewer sees the whole flow in one launch.
    full_packet_extras: dict[str, object] = {}
    if scenario_key == "crash_with_full_packet":
        full_packet_extras = _seed_crash_with_full_packet_extras(
            db,
            org_id=org_id,
            actor=actor,
            incident=incident,
            now_utc=now_utc,
            state=state,
        )

    db.commit()

    emit_audit_event(
        db,
        org_id=org_id,
        actor_type=DEMO_ACTOR_TYPE,
        actor_id=str(actor.id),
        action="demo.tenant.reseed",
        event_type="demo_tenant_reset",
        outcome="success",
        incident_id=incident.incident_id,
        export_id=export.export_id,
        metadata={"scenario_key": scenario_key, "seed_batch_id": seed_batch_id},
    )

    return {
        "scenario_id": definition.scenario_key,
        "seed_batch_id": seed_batch_id,
        "incident_id": str(incident.incident_id),
        "export_id": str(export.export_id),
        **full_packet_extras,
    }


def launch_scenario(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    scenario_id: str,
) -> dict[str, object]:
    """Reset tenant and seed selected scenario in a single orchestration call."""
    reset_demo_tenant(db, org_id=org_id, actor_id=str(actor.id), include_audit_record=False)
    seeded = seed_demo_tenant(db, org_id=org_id, actor=actor, scenario_key=scenario_id)

    emit_audit_event(
        db,
        org_id=org_id,
        actor_type=DEMO_ACTOR_TYPE,
        actor_id=str(actor.id),
        action="demo.scenario.launch",
        event_type="demo_scenario_launched",
        outcome="success",
        incident_id=uuid.UUID(str(seeded["incident_id"])),
        export_id=uuid.UUID(str(seeded["export_id"])),
        metadata={"scenario_id": scenario_id, "seed_batch_id": seeded["seed_batch_id"]},
    )
    return seeded


def ensure_demo_org(db: Session, *, org_id: uuid.UUID) -> Org:
    org = db.query(Org).filter(Org.id == org_id).first()
    if org is None:
        raise ValueError("org_not_found")
    return org


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — crash_with_full_packet supplemental seeding
# ─────────────────────────────────────────────────────────────────────────────


def _seed_crash_with_full_packet_extras(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    incident: Incident,
    now_utc: datetime,
    state: dict[str, object],
) -> dict[str, object]:
    """Add Phase 1+2+3 demo records on top of the base seed.

    Produces, for the seeded incident:

    * **Phase 2** — a :class:`Trailer` keyed by ``incident.adc_trailer_id``
      and three :class:`MaintenanceRecord` rows (mix of tractor + trailer,
      newest within the canonical 1-year window).
    * **Phase 1** — an active :class:`OrgNotificationRecipient` and a
      ``status='sent'`` :class:`CrashPacketDelivery` row, mirroring what
      the dispatch task would have produced. Useful for demoing the
      Phase 1 surface without standing up Celery + SES.
    * **Phase 3** — a finalized :class:`InsuranceFormTemplate` with
      mapped fields, then runs the real :func:`fill_form_for_incident`
      service to materialise an :class:`InsuranceFormFilling` row +
      ``insurance_form_filled`` :class:`Artifact`.

    Returns a dict of the new ids merged into the seeder's return payload
    so callers (and ``scripts/verify_demo.py``) can assert on them.
    """
    # We need a real Driver row so the canonical row's ``driver_json`` is
    # populated. Incident.adc_driver_id is opaque text; the canonical query
    # matches it as a UUID against drivers.driver_id, so we point the
    # incident at the new driver's UUID after creation.
    driver = Driver(
        org_id=org_id,
        # Phone is unique per row; salt with the org so re-seeds across
        # parallel test orgs don't collide.
        phone_e164=f"+1555{str(org_id.int)[-7:]}",
        display_name="Pat Demo-Driver",
        is_active=True,
    )
    db.add(driver)
    db.flush()

    db.add(
        DriverVehicleAssignment(
            org_id=org_id,
            driver_id=driver.driver_id,
            adc_vehicle_id=str(state["vehicle_id"]),
            source="manual",
        )
    )

    # Re-point the incident at the real driver UUID so the canonical row
    # join lands. ``adc_driver_id`` is plain text in the model.
    incident.adc_driver_id = str(driver.driver_id)

    # Phase 2 — trailer + maintenance.
    trailer = Trailer(
        org_id=org_id,
        adc_trailer_id=str(state["trailer_id"]),
        vin="TRDEMO00000000001",
        make="DemoTrailerCo",
        model="Reefer-53",
        year=2022,
        plate="DEMO-T1",
        last_inspection_at_utc=now_utc - timedelta(days=45),
        source="manual",
    )
    db.add(trailer)

    for offset_days, vendor, summary, asset_kind, asset_id in [
        (
            14,
            "ShopAlpha",
            "Pre-trip brake adjustment",
            "tractor",
            str(state["vehicle_id"]),
        ),
        (
            45,
            "ShopBeta",
            "Trailer ABS sensor replacement",
            "trailer",
            str(state["trailer_id"]),
        ),
        (
            120,
            "ShopAlpha",
            "Annual DOT inspection",
            "tractor",
            str(state["vehicle_id"]),
        ),
    ]:
        db.add(
            MaintenanceRecord(
                org_id=org_id,
                asset_kind=asset_kind,
                asset_id=asset_id,
                performed_at_utc=now_utc - timedelta(days=offset_days),
                vendor=vendor,
                summary=summary,
                mileage=100000 + offset_days * 100,
                source="manual",
            )
        )

    # Phase 1 — recipient + a "sent" delivery row.
    recipient = OrgNotificationRecipient(
        org_id=org_id,
        email="claims-demo@adc.local",
        full_name="Demo Claims Inbox",
        role_tag="claims",
        channels=["email"],
        active=True,
    )
    db.add(recipient)

    delivery_idempotency_key = f"demo-crashpacket-{incident.incident_id}"
    delivery = CrashPacketDelivery(
        incident_id=incident.incident_id,
        org_id=org_id,
        status="sent",
        target_sla_seconds=900,
        idempotency_key=delivery_idempotency_key,
        payload_hash="demo-payload-hash",
        sent_to=[{"email": recipient.email, "channel": "email"}],
        failed_to=[],
        message_ids=["demo-msg-1"],
        delivered_at_utc=now_utc - timedelta(minutes=1),
    )
    db.add(delivery)

    # Phase 3 — finalized template + inline fill of this incident.
    template = insurance_templates_repo.create_template(
        db,
        org_id=org_id,
        name="ACORD-DEMO",
        carrier="DemoMutual",
        created_by_user_id=actor.id,
    )
    add_field(
        db,
        template_id=template.id,
        spec=FieldSpec(
            name="DriverName",
            label="Driver Name",
            source_path="driver.display_name",
            transform="upper",
            required=True,
            sort_order=10,
        ),
    )
    add_field(
        db,
        template_id=template.id,
        spec=FieldSpec(
            name="VehicleUnit",
            label="Tractor unit",
            source_path="incident.adc_vehicle_id",
            sort_order=20,
        ),
    )
    add_field(
        db,
        template_id=template.id,
        spec=FieldSpec(
            name="TrailerVIN",
            label="Trailer VIN",
            source_path="trailer.vin",
            sort_order=30,
        ),
    )
    add_field(
        db,
        template_id=template.id,
        spec=FieldSpec(
            name="LastMaintVendor",
            label="Most recent maintenance vendor",
            source_path="maintenance[0].vendor",
            sort_order=40,
        ),
    )
    finalize_template(db, template_id=template.id)

    # Imported lazily to avoid a top-level cycle through the fill service
    # (which itself imports the repo modules).
    from app.services.insurance_form_fill_service import fill_form_for_incident

    db.flush()  # ensure trailer + maintenance + driver visible to fill query

    fill_result = fill_form_for_incident(
        db,
        incident_id=incident.incident_id,
        template_id=template.id,
    )

    return {
        "driver_id": str(driver.driver_id),
        "trailer_id": str(trailer.id),
        "recipient_id": str(recipient.id),
        "crash_packet_delivery_id": str(delivery.id),
        "insurance_form_template_id": str(template.id),
        "insurance_form_filling_id": str(fill_result.filling.id),
        "insurance_form_artifact_id": (
            str(fill_result.filling.output_artifact_id)
            if fill_result.filling.output_artifact_id
            else None
        ),
    }
