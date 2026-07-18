from __future__ import annotations

from collections import Counter

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.commercial.demo import (
    FEATURED_COLLISION_REF,
    FEATURED_COMPLETE_REF,
    FEATURED_THEFT_REF,
    seed_expanded_demo_workspace,
)
from app.core.security import hash_password
from app.db.models import (
    Base,
    Artifact,
    CaseNote,
    CaseTask,
    Driver,
    Event,
    Export,
    Incident,
    Org,
    OrgVehicleRegistry,
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
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _identity(db_session, name="Expanded Demo Org"):
    org = Org(name=name)
    db_session.add(org)
    db_session.commit()
    actor = User(
        email=f"admin-{name.replace(' ', '-').lower()}@adc.local",
        password_hash=hash_password("DemoAdmin!2345"),
        role=Role.ORG_ADMIN.value,
    )
    db_session.add(actor)
    db_session.commit()
    db_session.add(UserOrg(user_id=actor.id, org_id=org.id))
    db_session.commit()
    return org, actor


def _counts(db_session, org_id):
    incident_ids = [
        row.incident_id
        for row in db_session.query(Incident.incident_id).filter(
            Incident.org_id == org_id
        )
    ]
    return {
        "users": db_session.query(UserOrg).filter(UserOrg.org_id == org_id).count(),
        "drivers": db_session.query(Driver).filter(Driver.org_id == org_id).count(),
        "vehicles": db_session.query(OrgVehicleRegistry)
        .filter(OrgVehicleRegistry.org_id == org_id)
        .count(),
        "incidents": len(incident_ids),
        "evidence": db_session.query(Artifact)
        .filter(Artifact.org_id == org_id, Artifact.incident_id.in_(incident_ids))
        .count(),
        "tasks": db_session.query(CaseTask)
        .filter(CaseTask.org_id == org_id, CaseTask.incident_id.in_(incident_ids))
        .count(),
        "notes": db_session.query(CaseNote)
        .filter(CaseNote.org_id == org_id, CaseNote.incident_id.in_(incident_ids))
        .count(),
        "events": db_session.query(Event)
        .filter(Event.org_id == org_id, Event.incident_id.in_(incident_ids))
        .count(),
        "exports": db_session.query(Export)
        .filter(Export.org_id == org_id, Export.incident_id.in_(incident_ids))
        .count(),
    }


def test_expanded_demo_seed_is_dense_and_idempotent(db_session):
    org, actor = _identity(db_session)
    first = seed_expanded_demo_workspace(db_session, org_id=org.id, actor=actor)
    first_counts = _counts(db_session, org.id)
    second = seed_expanded_demo_workspace(db_session, org_id=org.id, actor=actor)
    assert first == second
    assert _counts(db_session, org.id) == first_counts
    assert first_counts["users"] >= 6
    assert first_counts["incidents"] >= 24
    assert first_counts["drivers"] >= 12
    assert first_counts["vehicles"] >= 12
    assert first_counts["evidence"] >= 60
    assert first_counts["tasks"] >= 40
    assert first_counts["notes"] >= 30
    assert first_counts["events"] >= 120
    assert first_counts["exports"] >= 18
    statuses = Counter(
        row.status for row in db_session.query(Export).filter(Export.org_id == org.id)
    )
    assert statuses["ready"] > 0
    assert statuses["failed"] >= 2
    assert statuses["processing"] > 0
    assert statuses["queued"] > 0
    for ref in (FEATURED_COLLISION_REF, FEATURED_THEFT_REF, FEATURED_COMPLETE_REF):
        assert ref in first["featured_incidents"]


def test_expanded_demo_seed_is_org_scoped(db_session):
    demo_org, actor = _identity(db_session, "Scoped Demo Org")
    other_org, other_actor = _identity(db_session, "Other Org")
    seed_expanded_demo_workspace(db_session, org_id=other_org.id, actor=other_actor)
    other_counts = _counts(db_session, other_org.id)
    seed_expanded_demo_workspace(db_session, org_id=demo_org.id, actor=actor)
    assert _counts(db_session, other_org.id) == other_counts
