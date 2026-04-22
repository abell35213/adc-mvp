from types import SimpleNamespace
from uuid import uuid4

from app.case_ops import metrics
from app.main import app


class _FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return []


class _FakeDB:
    def query(self, *_args, **_kwargs):
        return _FakeQuery()


def test_case_ops_incident_routes_are_registered_before_dynamic_incident_id_route():
    route_paths = [route.path for route in app.router.routes if hasattr(route, "path")]

    queue_index = route_paths.index("/incidents/queue")
    summary_index = route_paths.index("/incidents/summary-metrics")
    alerts_index = route_paths.index("/incidents/alerts")
    incident_id_index = route_paths.index("/incidents/{incident_id}")

    assert queue_index < incident_id_index
    assert summary_index < incident_id_index
    assert alerts_index < incident_id_index


def test_query_incident_queue_filters_blockers_before_paginating(monkeypatch):
    incident_a = SimpleNamespace(incident_id=uuid4())
    incident_b = SimpleNamespace(incident_id=uuid4())
    incident_c = SimpleNamespace(incident_id=uuid4())
    incidents = [incident_a, incident_b, incident_c]

    def _list_incident_queue(_db, **_kwargs):
        return incidents

    def _count_should_not_be_called(**_kwargs):  # pragma: no cover - guard clause
        raise AssertionError("count_incident_queue should not be called for blocker-filtered queries")

    blocker_totals = {
        incident_a.incident_id: (0, 0, 0),
        incident_b.incident_id: (2, 1, 1),
        incident_c.incident_id: (1, 1, 0),
    }

    def _build_snapshot(*, incident, **_kwargs):
        total, critical_count, important_count = blocker_totals[incident.incident_id]
        return SimpleNamespace(
            blockers=SimpleNamespace(
                total=total,
                critical_count=critical_count,
                important_count=important_count,
            )
        )

    monkeypatch.setattr(metrics, "list_incident_queue", _list_incident_queue)
    monkeypatch.setattr(metrics, "count_incident_queue", _count_should_not_be_called)
    monkeypatch.setattr(metrics, "_build_snapshot", _build_snapshot)
    monkeypatch.setattr(
        metrics,
        "_build_queue_item",
        lambda *, incident, snapshot: {
            "incident_id": incident.incident_id,
            "critical": snapshot.blockers.critical_count,
        },
    )

    page_1 = metrics.query_incident_queue(
        _FakeDB(),
        org_ids=[uuid4()],
        blockers="critical",
        page=1,
        page_size=1,
    )
    page_2 = metrics.query_incident_queue(
        _FakeDB(),
        org_ids=[uuid4()],
        blockers="critical",
        page=2,
        page_size=1,
    )

    assert page_1["total"] == 2
    assert page_1["items"] == [{"incident_id": incident_b.incident_id, "critical": 1}]
    assert page_2["total"] == 2
    assert page_2["items"] == [{"incident_id": incident_c.incident_id, "critical": 1}]
