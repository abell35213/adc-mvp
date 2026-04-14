import uuid
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Event, Incident, Org
from app.tasks.export_tasks import ExportRuntimeContext, _sync_incident_case_status_after_export


def test_sync_incident_case_status_after_export_moves_ready_for_export_to_exported():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    org = Org(name="Test Org")
    session.add(org)
    session.commit()
    session.refresh(org)

    incident = Incident(
        org_id=org.id,
        case_status="ready_for_export",
        readiness_state="ready_for_export",
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)

    ctx = ExportRuntimeContext(
        db=session,
        incident_uuid=incident.incident_id,
        export_uuid=uuid.uuid4(),
        incident_id=str(incident.incident_id),
        export_id=str(uuid.uuid4()),
        workflow_key="workflow",
        org_id=str(org.id),
        settings=SimpleNamespace(S3_BUCKET="bucket"),
        system_event_type=SimpleNamespace(INCIDENT_STATUS_CHANGED="incident_status_changed"),
        s3_key_builder=None,
        s3=None,
        export_row=SimpleNamespace(export_type="court_defense", options_json={}),
        incident_row=incident,
        warnings=[],
        missing_items=[],
        artifacts=[],
        events=[],
        exportable_artifacts=[],
        inventory_csv_bytes=b"",
        coc_csv_bytes=b"",
        appendix_csv_bytes=b"",
        readme_content="",
        zip_bytes=b"",
        zip_key=None,
    )

    _sync_incident_case_status_after_export(ctx)
    session.commit()
    session.refresh(incident)

    assert incident.case_status == "exported"
    assert incident.readiness_state == "exported"
    assert isinstance(incident.last_activity_at_utc, datetime)
    assert incident.last_activity_at_utc is not None

    status_event = session.query(Event).filter(Event.incident_id == incident.incident_id).one()
    assert status_event.event_type == "incident_status_changed"
    assert status_event.payload["from_case_status"] == "ready_for_export"
    assert status_event.payload["to_case_status"] == "exported"
