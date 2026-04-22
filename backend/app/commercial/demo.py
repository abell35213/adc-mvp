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
    DemoScenario,
    Event,
    Export,
    Incident,
    Org,
    OrgExportValidationRun,
    OrgOnboardingStepCompletion,
    OrgTestIncidentRun,
    User,
)
from app.onboarding.service import create_export_validation_run, create_test_incident_run, set_step_completion_override

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
