"""Tests for the incident queue/alert helpers in ``app.db.repo.incidents``.

These functions back the case-ops queue UI (filters + sort orders) and the
queue alert badges. They are pure SQL helpers so they're exercised against
an in-memory SQLite database with the production models.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Incident, Org, User
from app.db.repo import incidents as repo


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
    o = Org(name="Acme")
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def other_org(db_session):
    o = Org(name="Other")
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def owner_user(db_session, org):
    u = User(email="owner@acme.test", password_hash="x", role="safety_manager")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_incident(
    db_session,
    org,
    *,
    case_status: str = "new",
    readiness_state: str | None = None,
    owner_user_id: uuid.UUID | None = None,
    is_test: bool = False,
    adc_vehicle_id: str | None = None,
    samsara_vehicle_id: str | None = None,
    adc_driver_id: str | None = None,
    severity: str | None = None,
    created_at: datetime | None = None,
    last_activity_at: datetime | None = None,
    ready_for_export_at: datetime | None = None,
) -> Incident:
    inc = Incident(
        org_id=org.id,
        status="open",
        case_status=case_status,
        readiness_state=readiness_state,
        owner_user_id=owner_user_id,
        is_test_incident=is_test,
        adc_vehicle_id=adc_vehicle_id,
        samsara_vehicle_id=samsara_vehicle_id,
        adc_driver_id=adc_driver_id,
        severity=severity,
    )
    db_session.add(inc)
    db_session.flush()
    if created_at is not None:
        inc.created_at_utc = created_at
    if last_activity_at is not None:
        inc.last_activity_at_utc = last_activity_at
    if ready_for_export_at is not None:
        inc.ready_for_export_at_utc = ready_for_export_at
    db_session.commit()
    db_session.refresh(inc)
    return inc


# --- get_incident / list_incidents / create_incident ---


def test_get_incident_returns_incident_when_in_org(db_session, org):
    inc = _make_incident(db_session, org)
    result = repo.get_incident(db_session, inc.incident_id, org_ids=[org.id])
    assert result is not None
    assert result.incident_id == inc.incident_id


def test_get_incident_returns_none_when_org_mismatch(db_session, org, other_org):
    inc = _make_incident(db_session, org)
    assert repo.get_incident(db_session, inc.incident_id, org_ids=[other_org.id]) is None


def test_get_incident_no_org_filter_returns_any(db_session, org):
    inc = _make_incident(db_session, org)
    assert repo.get_incident(db_session, inc.incident_id) is not None


def test_list_incidents_excludes_test_incidents(db_session, org):
    real = _make_incident(db_session, org, is_test=False)
    _make_incident(db_session, org, is_test=True)
    rows = repo.list_incidents(db_session, org_ids=[org.id])
    assert [i.incident_id for i in rows] == [real.incident_id]


def test_list_incidents_respects_pagination(db_session, org):
    base_time = datetime.now(timezone.utc)
    created = [
        _make_incident(db_session, org, created_at=base_time + timedelta(minutes=i))
        for i in range(3)
    ]
    rows = repo.list_incidents(db_session, skip=1, limit=1, org_ids=[org.id])
    assert len(rows) == 1
    assert rows[0].incident_id != created[0].incident_id
    assert rows[0].incident_id in {
        created[1].incident_id,
        created[2].incident_id,
    }


def test_create_incident_persists_optional_fields(db_session, org):
    inc = repo.create_incident(
        db_session,
        status="open",
        adc_vehicle_id="adc-v1",
        samsara_vehicle_id="samsara-v1",
        adc_driver_id="d-1",
        severity="major",
        org_id=org.id,
        is_test_incident=True,
    )
    assert inc.incident_id is not None
    assert inc.adc_vehicle_id == "adc-v1"
    assert inc.is_test_incident is True


# --- list_incident_queue / count_incident_queue ---


def test_list_incident_queue_empty_when_no_orgs(db_session):
    assert repo.list_incident_queue(db_session, org_ids=[]) == []


def test_count_incident_queue_zero_when_no_orgs(db_session):
    assert repo.count_incident_queue(db_session, org_ids=[]) == 0


def test_list_incident_queue_filters_test_incidents_and_other_orgs(
    db_session, org, other_org
):
    keep = _make_incident(db_session, org)
    _make_incident(db_session, org, is_test=True)
    _make_incident(db_session, other_org)
    rows = repo.list_incident_queue(db_session, org_ids=[org.id])
    assert [i.incident_id for i in rows] == [keep.incident_id]
    assert repo.count_incident_queue(db_session, org_ids=[org.id]) == 1


def test_list_incident_queue_filters_by_case_status_owner_and_readiness(
    db_session, org, owner_user
):
    target = _make_incident(
        db_session,
        org,
        case_status="in_review",
        readiness_state="ready_for_export",
        owner_user_id=owner_user.id,
    )
    _make_incident(db_session, org, case_status="new")
    _make_incident(db_session, org, case_status="in_review", readiness_state="not_ready")

    rows = repo.list_incident_queue(
        db_session,
        org_ids=[org.id],
        case_status="in_review",
        owner_user_id=owner_user.id,
        readiness_state="ready_for_export",
    )
    assert [i.incident_id for i in rows] == [target.incident_id]
    assert (
        repo.count_incident_queue(
            db_session,
            org_ids=[org.id],
            case_status="in_review",
            owner_user_id=owner_user.id,
            readiness_state="ready_for_export",
        )
        == 1
    )


def test_list_incident_queue_filters_by_created_window(db_session, org):
    now = datetime.now(timezone.utc)
    old = _make_incident(db_session, org, created_at=now - timedelta(days=10))
    recent = _make_incident(db_session, org, created_at=now - timedelta(days=1))

    rows = repo.list_incident_queue(
        db_session,
        org_ids=[org.id],
        created_from_utc=now - timedelta(days=2),
    )
    assert [i.incident_id for i in rows] == [recent.incident_id]

    rows = repo.list_incident_queue(
        db_session,
        org_ids=[org.id],
        created_to_utc=now - timedelta(days=5),
    )
    assert [i.incident_id for i in rows] == [old.incident_id]


def test_list_incident_queue_search_matches_vehicle_driver_severity(db_session, org):
    a = _make_incident(db_session, org, adc_vehicle_id="TRUCK-42")
    b = _make_incident(db_session, org, adc_driver_id="driver-XYZ")
    c = _make_incident(db_session, org, samsara_vehicle_id="SAM-7")
    d = _make_incident(db_session, org, severity="major")

    assert {i.incident_id for i in repo.list_incident_queue(
        db_session, org_ids=[org.id], search="TRUCK"
    )} == {a.incident_id}
    assert {i.incident_id for i in repo.list_incident_queue(
        db_session, org_ids=[org.id], search="xyz"
    )} == {b.incident_id}
    assert {i.incident_id for i in repo.list_incident_queue(
        db_session, org_ids=[org.id], search="SAM-"
    )} == {c.incident_id}
    assert {i.incident_id for i in repo.list_incident_queue(
        db_session, org_ids=[org.id], search="major"
    )} == {d.incident_id}


def test_list_incident_queue_sort_urgency_orders_by_status_priority(db_session, org):
    closed = _make_incident(db_session, org, case_status="closed")
    new = _make_incident(db_session, org, case_status="new")
    escalated = _make_incident(db_session, org, case_status="escalated")
    rows = repo.list_incident_queue(db_session, org_ids=[org.id], sort="urgency")
    assert [i.incident_id for i in rows] == [
        escalated.incident_id,
        new.incident_id,
        closed.incident_id,
    ]


def test_list_incident_queue_sort_readiness_orders_by_readiness_priority(db_session, org):
    closed = _make_incident(db_session, org, readiness_state="closed")
    not_ready = _make_incident(db_session, org, readiness_state="not_ready")
    cond = _make_incident(db_session, org, readiness_state="conditionally_ready")
    rows = repo.list_incident_queue(db_session, org_ids=[org.id], sort="readiness")
    assert [i.incident_id for i in rows] == [
        not_ready.incident_id,
        cond.incident_id,
        closed.incident_id,
    ]


def test_list_incident_queue_default_sort_is_newest_first(db_session, org):
    now = datetime.now(timezone.utc)
    older = _make_incident(db_session, org, created_at=now - timedelta(days=2))
    newer = _make_incident(db_session, org, created_at=now - timedelta(hours=1))
    rows = repo.list_incident_queue(db_session, org_ids=[org.id])
    assert [i.incident_id for i in rows] == [newer.incident_id, older.incident_id]


def test_list_incident_queue_pagination(db_session, org):
    now = datetime.now(timezone.utc)
    incidents = [
        _make_incident(db_session, org, created_at=now - timedelta(days=4)),
        _make_incident(db_session, org, created_at=now - timedelta(days=3)),
        _make_incident(db_session, org, created_at=now - timedelta(days=2)),
        _make_incident(db_session, org, created_at=now - timedelta(days=1)),
        _make_incident(db_session, org, created_at=now),
    ]
    expected_ids = [i.incident_id for i in reversed(incidents)]
    rows = repo.list_incident_queue(db_session, org_ids=[org.id], skip=2, limit=2)
    assert len(rows) == 2
    assert [i.incident_id for i in rows] == expected_ids[2:4]


# --- count_incident_alerts ---


def test_count_incident_alerts_returns_zero_dict_when_no_orgs(db_session):
    out = repo.count_incident_alerts(
        db_session, org_ids=[], now_utc=datetime.now(timezone.utc)
    )
    assert out == {"stalled": 0, "unassigned": 0, "blocked": 0, "export_aging": 0}


def test_count_incident_alerts_classifies_each_alert_type(db_session, org, owner_user):
    now = datetime.now(timezone.utc)

    # stalled: open + last activity > 72h ago
    _make_incident(
        db_session,
        org,
        case_status="in_review",
        owner_user_id=owner_user.id,
        last_activity_at=now - timedelta(hours=80),
    )

    # unassigned: open + no owner
    _make_incident(db_session, org, case_status="in_review")

    # blocked: open + readiness_state == not_ready (and assigned, so not unassigned)
    _make_incident(
        db_session,
        org,
        case_status="in_review",
        readiness_state="not_ready",
        owner_user_id=owner_user.id,
        last_activity_at=now,  # avoid stalled bucket
    )

    # export_aging: ready_for_export + ready_for_export_at_utc > 48h ago
    _make_incident(
        db_session,
        org,
        case_status="ready_for_export",
        owner_user_id=owner_user.id,
        last_activity_at=now,
        ready_for_export_at=now - timedelta(hours=72),
    )

    # closed incidents must not contribute to non-export alerts
    _make_incident(
        db_session,
        org,
        case_status="closed",
        last_activity_at=now - timedelta(days=10),
    )

    # test incidents excluded from all buckets
    _make_incident(
        db_session,
        org,
        case_status="in_review",
        is_test=True,
        last_activity_at=now - timedelta(hours=80),
    )

    out = repo.count_incident_alerts(db_session, org_ids=[org.id], now_utc=now)
    assert out == {"stalled": 1, "unassigned": 1, "blocked": 1, "export_aging": 1}


def test_count_incident_alerts_ignores_recent_activity_and_recent_export_ready(
    db_session, org, owner_user
):
    now = datetime.now(timezone.utc)
    # recent activity -> not stalled
    _make_incident(
        db_session,
        org,
        case_status="in_review",
        owner_user_id=owner_user.id,
        last_activity_at=now - timedelta(hours=1),
    )
    # ready_for_export less than 48h ago -> not export_aging
    _make_incident(
        db_session,
        org,
        case_status="ready_for_export",
        owner_user_id=owner_user.id,
        ready_for_export_at=now - timedelta(hours=1),
    )
    out = repo.count_incident_alerts(db_session, org_ids=[org.id], now_utc=now)
    assert out["stalled"] == 0
    assert out["export_aging"] == 0
