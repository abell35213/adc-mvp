"""Tests for ``app.db.repo.integration_connections``.

Validates that ``create_integration_connection`` persists provided fields
with sensible defaults and that ``list_integration_connections`` honours
each filter argument in isolation and in combination.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Org
from app.db.repo import integration_connections as repo


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


def test_create_integration_connection_round_trip(db_session, org):
    conn = repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="org-ext-1",
        credentials_ref="vault://samsara/acme",
        config_json={"region": "us"},
    )
    assert conn.connection_id is not None
    assert conn.org_id == org.id
    assert conn.provider == "samsara"
    assert conn.domain == "dashcam"
    assert conn.status == "active"
    assert conn.external_reference == "org-ext-1"
    assert conn.credentials_ref == "vault://samsara/acme"
    assert conn.config_json == {"region": "us"}


def test_create_integration_connection_defaults(db_session, org):
    conn = repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="motive",
    )
    assert conn.status == "pending"
    assert conn.domain is None
    assert conn.external_reference is None
    assert conn.credentials_ref is None
    assert conn.config_json == {}


def test_list_integration_connections_filters_each_field(db_session, org, other_org):
    a = repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="ext-A",
    )
    repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="motive",
        domain="telematics",
        status="pending",
        external_reference="ext-B",
    )
    repo.create_integration_connection(
        db_session,
        org_id=other_org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="ext-C",
    )

    by_org = repo.list_integration_connections(db_session, org_id=org.id)
    assert {c.external_reference for c in by_org} == {"ext-A", "ext-B"}

    by_provider = repo.list_integration_connections(db_session, provider="samsara")
    assert {c.external_reference for c in by_provider} == {"ext-A", "ext-C"}

    by_domain = repo.list_integration_connections(db_session, domain="telematics")
    assert [c.external_reference for c in by_domain] == ["ext-B"]

    by_status = repo.list_integration_connections(db_session, status="pending")
    assert [c.external_reference for c in by_status] == ["ext-B"]

    by_ref = repo.list_integration_connections(db_session, external_reference="ext-A")
    assert [c.connection_id for c in by_ref] == [a.connection_id]


def test_list_integration_connections_combined_filters(db_session, org, other_org):
    repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="want",
    )
    repo.create_integration_connection(
        db_session,
        org_id=other_org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="want",
    )
    repo.create_integration_connection(
        db_session,
        org_id=org.id,
        provider="samsara",
        domain="telematics",
        status="active",
        external_reference="want",
    )
    rows = repo.list_integration_connections(
        db_session,
        org_id=org.id,
        provider="samsara",
        domain="dashcam",
        status="active",
        external_reference="want",
    )
    assert len(rows) == 1
    assert rows[0].org_id == org.id


def test_list_integration_connections_no_filters_returns_all(db_session, org):
    repo.create_integration_connection(db_session, org_id=org.id, provider="p1")
    repo.create_integration_connection(db_session, org_id=org.id, provider="p2")
    assert len(repo.list_integration_connections(db_session)) == 2


def test_list_integration_connections_returns_empty_when_no_matches(db_session, org):
    repo.create_integration_connection(db_session, org_id=org.id, provider="samsara")
    assert (
        repo.list_integration_connections(db_session, provider="does-not-exist") == []
    )
