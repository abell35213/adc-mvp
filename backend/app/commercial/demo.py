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
    CaseNote,
    CaseTask,
    CrashPacketDelivery,
    DemoScenario,
    DispatchInstruction,
    Driver,
    DriverVehicleAssignment,
    Event,
    Export,
    Incident,
    InsuranceFormFilling,
    InsuranceFormTemplate,
    LoadingDockReport,
    MaintenanceRecord,
    Org,
    OrgExportValidationRun,
    OrgVehicleRegistry,
    OrgNotificationRecipient,
    OrgOnboardingStepCompletion,
    OrgTestIncidentRun,
    Trailer,
    User,
    UserOrg,
    WeighStationReport,
)
from app.onboarding.service import (
    create_export_validation_run,
    create_test_incident_run,
    set_step_completion_override,
)
from app.services.insurance_form_template_service import (
    FieldSpec,
    add_field,
    finalize_template,
)
from app.db.repo import insurance_form_templates as insurance_templates_repo
from app.core.security import hash_password
from app.security.permissions import Role

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
    # Phase 3: dispatch / weigh / loading dock evidence seeded for the demo
    # accident. Photos linked via ``loading_dock_report_id`` cascade-delete
    # automatically when the LoadingDockReport row goes away.
    db.query(WeighStationReport).filter(
        WeighStationReport.org_id == org_id,
        WeighStationReport.ticket_number.like("WS-DEMO-%"),
    ).delete(synchronize_session=False)
    db.query(LoadingDockReport).filter(
        LoadingDockReport.org_id == org_id,
        LoadingDockReport.facility_name.like("Demo Loading Dock%"),
    ).delete(synchronize_session=False)
    db.query(DispatchInstruction).filter(
        DispatchInstruction.org_id == org_id,
        DispatchInstruction.dispatch_id.like("DSP-DEMO-%"),
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
        db.query(Driver).filter(Driver.driver_id.in_(demo_driver_ids)).delete(
            synchronize_session=False
        )
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
    db.query(OrgExportValidationRun).filter(
        OrgExportValidationRun.org_id == org_id
    ).delete(synchronize_session=False)
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
        progress_stage="ready_for_download"
        if export_status == "ready"
        else "assembling_documents",
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
            seed_metadata_json={
                "incident_id": str(incident.incident_id),
                "test_run_id": str(run.run_id),
            },
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


DEMO_REFERENCE_DATE = datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc)
DEMO_NAMESPACE = uuid.UUID("7d8de451-20ab-4c76-a0fc-f3d0f4adc001")
FEATURED_COLLISION_REF = "ADC-DEMO-2026-001"
FEATURED_THEFT_REF = "ADC-DEMO-2026-002"
FEATURED_COMPLETE_REF = "ADC-DEMO-2026-003"
DEMO_INCIDENT_REFS = (
    FEATURED_COLLISION_REF,
    FEATURED_THEFT_REF,
    FEATURED_COMPLETE_REF,
) + tuple(f"ADC-DEMO-2026-{index:03d}" for index in range(4, 27))


def _demo_uuid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(DEMO_NAMESPACE, f"{kind}:{key}")


def _demo_time(days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
    return DEMO_REFERENCE_DATE + timedelta(days=days, hours=hours, minutes=minutes)


def seed_expanded_demo_workspace(
    db: Session, *, org_id: uuid.UUID, actor: User
) -> dict[str, object]:
    """Seed the broad deterministic commercial-trucking demo workspace."""
    _ensure_demo_users(db, org_id=org_id, actor=actor)
    drivers = _seed_demo_drivers(db, org_id=org_id)
    vehicles = _seed_demo_vehicles(db, org_id=org_id, drivers=drivers)
    users = (
        db.query(User)
        .join(UserOrg, UserOrg.user_id == User.id)
        .filter(UserOrg.org_id == org_id)
        .order_by(User.email.asc())
        .all()
    )
    incidents = _seed_demo_incidents(
        db, org_id=org_id, users=users, drivers=drivers, vehicles=vehicles
    )
    _seed_demo_case_content(
        db, org_id=org_id, actor=actor, users=users, incidents=incidents
    )
    db.commit()
    return {
        "reference_date": DEMO_REFERENCE_DATE.isoformat(),
        "featured_incidents": [
            FEATURED_COLLISION_REF,
            FEATURED_THEFT_REF,
            FEATURED_COMPLETE_REF,
        ],
        "incident_count": len(incidents),
        "driver_count": len(drivers),
        "vehicle_count": len(vehicles),
    }


def _ensure_demo_users(db: Session, *, org_id: uuid.UUID, actor: User) -> None:
    people = [
        ("claims.director@adc.local", "Claims Director", Role.ORG_ADMIN.value),
        ("safety.manager@adc.local", "Safety Manager", Role.SAFETY_MANAGER.value),
        ("fleet.manager@adc.local", "Fleet Manager", Role.SAFETY_MANAGER.value),
        ("claims.analyst@adc.local", "Claims Analyst", Role.CLAIMS_USER.value),
        ("legal.ops@adc.local", "Legal Operations Specialist", Role.CLAIMS_USER.value),
    ]
    for email, name, role in people:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(
                id=_demo_uuid("user", email),
                email=email,
                password_hash=hash_password("DemoUser!2345"),
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
        else:
            user.role = role
            user.is_active = True
        if (
            db.query(UserOrg)
            .filter(UserOrg.user_id == user.id, UserOrg.org_id == org_id)
            .first()
            is None
        ):
            db.add(UserOrg(user_id=user.id, org_id=org_id))
    if (
        db.query(UserOrg)
        .filter(UserOrg.user_id == actor.id, UserOrg.org_id == org_id)
        .first()
        is None
    ):
        db.add(UserOrg(user_id=actor.id, org_id=org_id))


def _seed_demo_drivers(db: Session, *, org_id: uuid.UUID) -> list[Driver]:
    names = [
        "Marion Hayes",
        "Elena Brooks",
        "Victor Chen",
        "Simone Reed",
        "Caleb Ortiz",
        "Nina Patel",
        "Jonah Price",
        "Avery Morgan",
        "Tessa Grant",
        "Luis Romero",
        "Dana Shaw",
        "Owen Parker",
        "Priya Nair",
        "Marcus Bell",
    ]
    out = []
    for i, name in enumerate(names, 1):
        phone = f"+1555{str(org_id.int)[-4:]}{i:03d}"
        d = db.query(Driver).filter(Driver.phone_e164 == phone).one_or_none()
        if d is None:
            d = Driver(
                driver_id=_demo_uuid("driver", f"{org_id}:{name}"),
                org_id=org_id,
                phone_e164=phone,
                display_name=name,
                is_active=i not in {9},
            )
            db.add(d)
            db.flush()
        else:
            d.org_id = org_id
            d.display_name = name
            d.is_active = i not in {9}
        out.append(d)
    return out


def _seed_demo_vehicles(
    db: Session, *, org_id: uuid.UUID, drivers: list[Driver]
) -> list[OrgVehicleRegistry]:
    out = []
    for i in range(1, 15):
        unit = f"ADC-{4200 + i}"
        v = (
            db.query(OrgVehicleRegistry)
            .filter(
                OrgVehicleRegistry.org_id == org_id,
                OrgVehicleRegistry.unit_number == unit,
            )
            .one_or_none()
        )
        if v is None:
            v = OrgVehicleRegistry(
                vehicle_id=_demo_uuid("vehicle", f"{org_id}:{unit}"),
                org_id=org_id,
                unit_number=unit,
                vin=f"1ADCDMO{i:010d}X",
                provider="demo",
                provider_vehicle_id=f"veh-demo-{i:03d}",
                is_active=i not in {12},
                qr_deployment_status="confirmed" if i < 11 else "distributed",
                license_plate=f"D{i:05d}",
                license_state="GA" if i < 6 else "TN",
                dot_unit_type="tractor",
            )
            db.add(v)
            db.flush()
        out.append(v)
        db.query(DriverVehicleAssignment).filter(
            DriverVehicleAssignment.org_id == org_id,
            DriverVehicleAssignment.adc_vehicle_id == unit,
        ).delete(synchronize_session=False)
        db.add(
            DriverVehicleAssignment(
                assignment_id=_demo_uuid("assignment", f"{org_id}:{unit}"),
                org_id=org_id,
                driver_id=drivers[(i - 1) % len(drivers)].driver_id,
                adc_vehicle_id=unit,
                assigned_at_utc=_demo_time(days=-30 + i),
                source="manual",
            )
        )
    return out


def _seed_demo_incidents(
    db: Session,
    *,
    org_id: uuid.UUID,
    users: list[User],
    drivers: list[Driver],
    vehicles: list[OrgVehicleRegistry],
) -> list[Incident]:
    statuses = [
        "escalated",
        "awaiting_evidence",
        "ready_for_export",
        "new",
        "in_review",
        "awaiting_evidence",
        "ready_for_export",
        "in_review",
        "awaiting_follow_up",
        "closed",
        "exported",
        "escalated",
        "new",
        "awaiting_evidence",
        "in_review",
        "ready_for_export",
        "closed",
        "awaiting_follow_up",
        "in_review",
        "new",
        "ready_for_export",
        "awaiting_evidence",
        "escalated",
        "closed",
        "in_review",
        "awaiting_follow_up",
    ]
    readiness = [
        "not_ready",
        "not_ready",
        "ready_for_export",
        "not_ready",
        "conditionally_ready",
        "not_ready",
        "ready_for_export",
        "conditionally_ready",
        "not_ready",
        "closed",
        "exported",
        "not_ready",
        "not_ready",
        "not_ready",
        "conditionally_ready",
        "ready_for_export",
        "closed",
        "conditionally_ready",
        "conditionally_ready",
        "not_ready",
        "ready_for_export",
        "not_ready",
        "not_ready",
        "closed",
        "conditionally_ready",
        "conditionally_ready",
    ]
    out = []
    for i, ref in enumerate(DEMO_INCIDENT_REFS):
        inc = (
            db.query(Incident)
            .filter(Incident.incident_id == _demo_uuid("incident", f"{org_id}:{ref}"))
            .one_or_none()
        )
        vehicle = vehicles[i % len(vehicles)]
        driver = drivers[i % len(drivers)]
        owner = users[(i + 1) % len(users)].id if i not in {3, 12, 19} else None
        if inc is None:
            inc = Incident(
                incident_id=_demo_uuid("incident", f"{org_id}:{ref}"), org_id=org_id
            )
            db.add(inc)
        inc.status = (
            "closed"
            if statuses[i] == "closed"
            else ("accident_occurred" if i in {0, 1, 11, 22} else "evidence_capturing")
        )
        inc.case_status = statuses[i]
        inc.severity = (
            "serious"
            if i in {0, 1, 11, 22}
            else ("minor" if i in {2, 9, 16, 23} else "moderate")
        )
        inc.adc_vehicle_id = vehicle.unit_number
        inc.samsara_vehicle_id = vehicle.provider_vehicle_id
        inc.adc_driver_id = str(driver.driver_id)
        inc.team_queue = "Southeast Claims"
        inc.owner_user_id = owner
        inc.owner_assigned_by_user_id = users[0].id if owner else None
        inc.owner_assigned_at_utc = _demo_time(days=-8 + i) if owner else None
        inc.created_at_utc = _demo_time(days=-(20 - i % 10), hours=i)
        inc.last_activity_at_utc = (
            _demo_time(days=-5, hours=i)
            if i in {5, 13, 21}
            else _demo_time(days=-(i % 4), hours=i)
        )
        inc.ready_for_export_at_utc = (
            _demo_time(days=-3, hours=i) if statuses[i] == "ready_for_export" else None
        )
        inc.readiness_state = readiness[i]
        inc.completeness_percent = [
            58,
            62,
            94,
            35,
            72,
            49,
            88,
            76,
            54,
            100,
            100,
            40,
            28,
            51,
            79,
            91,
            100,
            73,
            82,
            33,
            89,
            47,
            44,
            100,
            78,
            70,
        ][i]
        inc.completeness_status = (
            "ready" if inc.completeness_percent >= 88 else "needs_follow_up"
        )
        inc.is_test_incident = False
        out.append(inc)
    db.flush()
    return out


def _seed_demo_case_content(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    users: list[User],
    incidents: list[Incident],
) -> None:
    ids = [i.incident_id for i in incidents]
    for model in (Artifact, CaseTask, CaseNote, Event, Export):
        db.query(model).filter(
            model.org_id == org_id, model.incident_id.in_(ids)
        ).delete(synchronize_session=False)
    artifact_types = [
        "photo",
        "driver_statement",
        "police_report",
        "dash_cam_video_road",
        "vehicle_inspection",
        "eld_log",
        "insurance_document",
        "witness_information",
        "bill_of_lading",
        "cargo_inventory",
        "repair_estimate",
        "supporting_correspondence",
    ]
    task_titles = [
        "Request police report",
        "Obtain driver statement",
        "Review scene photos",
        "Review dashcam footage",
        "Confirm vehicle inspection",
        "Contact insurance carrier",
        "Collect witness statement",
        "Request bill of lading",
        "Review cargo inventory",
        "Generate defense packet",
    ]
    note_bodies = [
        "Initial intake reviewed and triage level confirmed.",
        "Driver contacted; statement request sent.",
        "Police report request submitted to responding agency.",
        "Insurance carrier notified and claim reference added.",
        "Evidence quality reviewed for export readiness.",
        "Legal review requested for preservation posture.",
    ]
    for idx, inc in enumerate(incidents):
        per_art = 4 if idx > 2 else (8 if idx == 0 else 7)
        for j in range(per_art):
            status = (
                "unavailable"
                if (idx + j) % 11 == 0
                else "pending"
                if (idx + j) % 4 == 0
                else "captured"
            )
            if idx == 0 and artifact_types[j] == "police_report":
                status = "pending"
            db.add(
                Artifact(
                    artifact_id=_demo_uuid("artifact", f"{inc.incident_id}:{j}"),
                    org_id=org_id,
                    incident_id=inc.incident_id,
                    artifact_type=artifact_types[j % len(artifact_types)],
                    status=status,
                    capture_window_start_utc=_demo_time(days=-idx - 1),
                    capture_window_end_utc=_demo_time(days=-idx),
                    uploaded_at_utc=_demo_time(days=-idx, hours=j)
                    if status == "captured"
                    else None,
                    unavailable_reason_code="not_applicable"
                    if status == "unavailable"
                    else None,
                    unavailable_reason_detail="Agency advised no separate report is available."
                    if status == "unavailable"
                    else None,
                    sha256="0" * 64 if status == "captured" else None,
                    byte_size=1024 + j if status == "captured" else None,
                )
            )
        for j in range(2 if idx < 20 else 1):
            st = (
                "completed"
                if (idx + j) % 3 == 0
                else ("blocked" if (idx + j) % 7 == 0 else "open")
            )
            due = (
                _demo_time(days=-2 + j)
                if idx in {0, 3, 5, 11, 13, 19, 22} and st != "completed"
                else _demo_time(days=1 + j)
            )
            db.add(
                CaseTask(
                    task_id=_demo_uuid("task", f"{inc.incident_id}:{j}"),
                    org_id=org_id,
                    incident_id=inc.incident_id,
                    title=task_titles[(idx + j) % len(task_titles)],
                    description="Deterministic demo follow-up for case operations.",
                    task_type=["review", "evidence", "follow_up", "export", "other"][
                        (idx + j) % 5
                    ],
                    status=st,
                    priority=["urgent", "high", "medium", "low"][(idx + j) % 4],
                    due_at_utc=due,
                    assigned_to_user_id=(
                        actor.id
                        if (idx + j) % 2 == 0
                        else users[(idx + j) % len(users)].id
                    ),
                    assigned_at_utc=_demo_time(days=-idx),
                    assigned_by_user_id=actor.id,
                    created_by_user_id=actor.id,
                    completed_at_utc=_demo_time(days=-1) if st == "completed" else None,
                    completed_by_user_id=actor.id if st == "completed" else None,
                    created_at_utc=_demo_time(days=-idx, minutes=j),
                )
            )
        for j in range(2 if idx < 16 else 1):
            db.add(
                CaseNote(
                    note_id=_demo_uuid("note", f"{inc.incident_id}:{j}"),
                    org_id=org_id,
                    incident_id=inc.incident_id,
                    body=note_bodies[(idx + j) % len(note_bodies)],
                    note_type="decision" if j == 1 and idx % 5 == 0 else "standard",
                    tags_json=["demo", "priority"] if idx in {0, 1} else ["demo"],
                    created_by_user_id=users[(idx + j) % len(users)].id,
                    created_at_utc=_demo_time(days=-idx, hours=j),
                )
            )
        for j in range(5 if idx < 24 else 4):
            db.add(
                Event(
                    id=_demo_uuid("event", f"{inc.incident_id}:{j}"),
                    org_id=org_id,
                    incident_id=inc.incident_id,
                    event_type=[
                        "incident_created",
                        "owner_assigned",
                        "evidence_requested",
                        "evidence_received",
                        "task_created",
                        "note_added",
                        "readiness_recalculated",
                        "export_requested",
                        "export_failed",
                    ][(idx + j) % 9],
                    actor_type="user",
                    actor_id=str(users[(idx + j) % len(users)].id),
                    occurred_at_utc=_demo_time(days=-idx, hours=j),
                    payload={
                        "case_reference": DEMO_INCIDENT_REFS[idx],
                        "title": inc.adc_vehicle_id,
                    },
                )
            )
        if idx < 22:
            status = [
                "ready",
                "queued",
                "processing",
                "failed",
                "requested",
                "ready",
                "expired",
            ][idx % 7]
            parent = None
            if idx == 4:
                parent = _demo_uuid("export", f"{inc.incident_id}:failed-parent")
                db.add(
                    Export(
                        export_id=parent,
                        org_id=org_id,
                        incident_id=inc.incident_id,
                        export_type="court_defense",
                        profile_id="court_defense_v1",
                        requested_by_user_id=actor.id,
                        status="failed",
                        progress_stage="assembling_documents",
                        error_message="missing required evidence",
                        artifact_count=per_art,
                        timeline_event_count=5,
                        requested_at_utc=_demo_time(days=-idx, hours=1),
                        processing_started_at_utc=_demo_time(days=-idx, hours=2),
                    )
                )
            db.add(
                Export(
                    export_id=_demo_uuid("export", f"{inc.incident_id}:main"),
                    org_id=org_id,
                    incident_id=inc.incident_id,
                    export_type=[
                        "court_defense",
                        "insurer_packet",
                        "internal_review",
                        "compliance_audit",
                    ][idx % 4],
                    profile_id="demo_packet_v1",
                    requested_by_user_id=actor.id,
                    retry_parent_export_id=parent,
                    status=status,
                    progress_stage="ready_for_download"
                    if status in {"ready", "expired"}
                    else (
                        [
                            "request_accepted",
                            "gathering_incident_data",
                            "assembling_documents",
                            "packaging_evidence",
                            "uploading_export",
                        ][idx % 5]
                    ),
                    error_message="document rendering failure"
                    if status == "failed"
                    else None,
                    package_sha256="1" * 64 if status in {"ready", "expired"} else None,
                    byte_size=4096 + idx if status in {"ready", "expired"} else None,
                    artifact_count=per_art,
                    timeline_event_count=5,
                    requested_at_utc=_demo_time(days=-idx),
                    processing_started_at_utc=_demo_time(days=-idx, hours=1)
                    if status in {"processing", "ready", "failed", "expired"}
                    else None,
                    completed_at_utc=_demo_time(days=-idx, hours=2)
                    if status in {"ready", "expired"}
                    else None,
                    expires_at_utc=_demo_time(days=-1)
                    if status == "expired"
                    else _demo_time(days=14)
                    if status == "ready"
                    else None,
                    s3_bucket="demo-artifacts"
                    if status in {"ready", "expired"}
                    else None,
                    s3_key=f"exports/{inc.incident_id}.zip"
                    if status in {"ready", "expired"}
                    else None,
                )
            )


def launch_scenario(
    db: Session,
    *,
    org_id: uuid.UUID,
    actor: User,
    scenario_id: str,
) -> dict[str, object]:
    """Reset tenant and seed selected scenario in a single orchestration call."""
    reset_demo_tenant(
        db, org_id=org_id, actor_id=str(actor.id), include_audit_record=False
    )
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

    # Phase 3 — dispatch / weigh / loading dock evidence.
    #
    # All three rows are linked directly to the demo incident so the marketing
    # flow visibly exercises the new crash-brief sections + their compliance
    # callouts (forced dispatch, over-weight ticket, improperly-loaded cargo).
    dispatch = DispatchInstruction(
        org_id=org_id,
        incident_id=incident.incident_id,
        adc_driver_id=str(driver.driver_id),
        adc_vehicle_id=str(state["vehicle_id"]),
        adc_trailer_id=str(state["trailer_id"]),
        dispatch_id="DSP-DEMO-001",
        load_number="LD-DEMO-9001",
        dispatched_by="Jane Dispatcher",
        dispatched_at_utc=now_utc - timedelta(hours=8),
        pickup_appointment_at_utc=now_utc - timedelta(hours=4),
        delivery_appointment_at_utc=now_utc + timedelta(hours=10),
        eta_at_utc=now_utc + timedelta(hours=9),
        origin_address="100 Origin Way, Albany NY",
        destination_address="900 Destination Blvd, Boston MA",
        hos_remaining_drive_minutes=45,
        hos_remaining_duty_minutes=120,
        forced_dispatch_flag=True,
        notes="Reefer set to 34F",
        source="manual",
    )
    db.add(dispatch)
    db.flush()

    weigh = WeighStationReport(
        org_id=org_id,
        incident_id=incident.incident_id,
        adc_vehicle_id=str(state["vehicle_id"]),
        adc_trailer_id=str(state["trailer_id"]),
        dispatch_instruction_id=dispatch.id,
        weighed_at_utc=now_utc - timedelta(hours=2),
        station_name="Demo Scale",
        station_location="I-90 mile 215",
        ticket_number="WS-DEMO-12345",
        gross_weight_lb=82500,
        steer_axle_weight_lb=12000,
        drive_axle_weight_lb=35000,
        trailer_axle_weight_lb=35500,
        legal_limit_lb=80000,
        is_over_legal_limit=True,
        result="cited",
        citation_text="Cited: drive-axle 35,000 lb (limit 34,000 lb)",
        inspector_name="Officer Smith",
        source="manual",
    )
    db.add(weigh)

    dock = LoadingDockReport(
        org_id=org_id,
        incident_id=incident.incident_id,
        adc_trailer_id=str(state["trailer_id"]),
        adc_vehicle_id=str(state["vehicle_id"]),
        dispatch_instruction_id=dispatch.id,
        loaded_at_utc=now_utc - timedelta(hours=6),
        facility_name="Demo Loading Dock A",
        facility_address="789 Dock Rd, Albany NY",
        commodity="Refrigerated produce (24 pallets)",
        pieces=24,
        gross_weight_lb=41000,
        net_weight_lb=38000,
        seal_number="SEAL-DEMO-77",
        securement_method="load bars + ratchet straps",
        weight_distribution_notes="Heavy on rear axle — shifted during loading",
        is_overloaded=False,
        is_improperly_loaded=True,
        loaded_by="Demo Dock Worker",
        dock_supervisor="Sue Supervisor",
        source="manual",
    )
    db.add(dock)
    db.flush()

    # Two photos linked many-to-one via Artifact.loading_dock_report_id.
    for label in ("dock-rear", "dock-left-axle"):
        db.add(
            Artifact(
                org_id=org_id,
                incident_id=incident.incident_id,
                artifact_type="loading_dock_photo",
                status="captured",
                s3_bucket="adc-mvp-artifacts",
                s3_key=f"demo/loading_dock/{label}.jpg",
                loading_dock_report_id=dock.id,
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
