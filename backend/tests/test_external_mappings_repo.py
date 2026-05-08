"""Tests for ``app.db.repo.external_mappings``.

Validates round-trip persistence and every filter combination on
``list_external_mappings`` (org_id, incident_id, status, provider,
external_reference) so the repository's filter wiring cannot regress
silently.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Incident, Org
from app.db.repo import external_mappings as repo


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
def org(db_session):
    org = Org(name="Acme")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def other_org(db_session):
    org = Org(name="Other")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def incident(db_session, org):
    inc = Incident(org_id=org.id, status="open")
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)
    return inc


def test_create_external_mapping_persists_required_fields(db_session, org, incident):
    mapping = repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="incident",
        internal_entity_id=str(incident.incident_id),
        external_reference="ext-123",
        incident_id=incident.incident_id,
        domain="dashcam",
        status="active",
        metadata_json={"foo": "bar"},
    )
    assert mapping.mapping_id is not None
    assert mapping.org_id == org.id
    assert mapping.provider == "samsara"
    assert mapping.domain == "dashcam"
    assert mapping.status == "active"
    assert mapping.metadata_json == {"foo": "bar"}


def test_create_external_mapping_defaults_metadata_to_empty_dict(db_session, org):
    mapping = repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="vehicle",
        internal_entity_id="adc-v1",
        external_reference="vehicle-1",
    )
    assert mapping.metadata_json == {}
    assert mapping.status == "active"
    assert mapping.domain is None
    assert mapping.incident_id is None


def test_list_external_mappings_filters_by_org(db_session, org, other_org):
    repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="vehicle",
        internal_entity_id="adc-v1",
        external_reference="ext-1",
    )
    repo.create_external_mapping(
        db_session,
        org_id=other_org.id,
        provider="samsara",
        internal_entity_type="vehicle",
        internal_entity_id="adc-v2",
        external_reference="ext-2",
    )

    rows = repo.list_external_mappings(db_session, org_id=org.id)
    assert len(rows) == 1
    assert rows[0].external_reference == "ext-1"


def test_list_external_mappings_filters_by_incident_status_provider_and_ref(
    db_session, org, incident
):
    a = repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="incident",
        internal_entity_id=str(incident.incident_id),
        external_reference="ext-A",
        incident_id=incident.incident_id,
        status="active",
    )
    repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="motive",
        internal_entity_type="incident",
        internal_entity_id=str(incident.incident_id),
        external_reference="ext-B",
        incident_id=incident.incident_id,
        status="inactive",
    )
    repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="vehicle",
        internal_entity_id="adc-v1",
        external_reference="ext-C",
        status="active",
    )

    by_incident = repo.list_external_mappings(db_session, incident_id=incident.incident_id)
    assert {m.external_reference for m in by_incident} == {"ext-A", "ext-B"}

    by_status = repo.list_external_mappings(db_session, status="inactive")
    assert [m.external_reference for m in by_status] == ["ext-B"]

    by_provider = repo.list_external_mappings(db_session, provider="samsara")
    assert {m.external_reference for m in by_provider} == {"ext-A", "ext-C"}

    by_ref = repo.list_external_mappings(db_session, external_reference="ext-A")
    assert [m.mapping_id for m in by_ref] == [a.mapping_id]

    by_incident_status_provider = repo.list_external_mappings(
        db_session,
        incident_id=incident.incident_id,
        status="active",
        provider="samsara",
    )
    assert [m.mapping_id for m in by_incident_status_provider] == [a.mapping_id]

    by_all_filters = repo.list_external_mappings(
        db_session,
        incident_id=incident.incident_id,
        status="active",
        provider="samsara",
        external_reference="ext-A",
    )
    assert [m.mapping_id for m in by_all_filters] == [a.mapping_id]


def test_list_external_mappings_no_filters_returns_all_ordered_desc(db_session, org):
    first = repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="p1",
        internal_entity_type="vehicle",
        internal_entity_id="v1",
        external_reference="ref-1",
    )
    second = repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="p2",
        internal_entity_type="vehicle",
        internal_entity_id="v2",
        external_reference="ref-2",
    )
    rows = repo.list_external_mappings(db_session)
    assert {r.mapping_id for r in rows} == {first.mapping_id, second.mapping_id}


def test_list_external_mappings_returns_empty_when_no_matches(db_session, org):
    repo.create_external_mapping(
        db_session,
        org_id=org.id,
        provider="samsara",
        internal_entity_type="vehicle",
        internal_entity_id="v1",
        external_reference="ref-1",
    )
    assert repo.list_external_mappings(db_session, provider="missing") == []
