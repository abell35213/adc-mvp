from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_liveness_is_up() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_healthy_dependencies(monkeypatch) -> None:
    from app.health import routes
    from app.health.checks import CheckResult

    client = TestClient(app)
    monkeypatch.setattr(routes, "check_database", lambda: CheckResult(ok=True, detail="reachable"))
    monkeypatch.setattr(routes, "check_redis", lambda: CheckResult(ok=True, detail="reachable"))
    monkeypatch.setattr(
        routes,
        "check_storage",
        lambda deep=False: CheckResult(ok=True, detail="skipped" if not deep else "ok"),
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True


def test_readiness_returns_503_when_meaningful_traffic_cannot_be_served(monkeypatch) -> None:
    from app.health import routes
    from app.health.checks import CheckResult

    client = TestClient(app)
    monkeypatch.setattr(
        routes,
        "check_database",
        lambda: CheckResult(ok=False, detail="OperationalError: db unavailable"),
    )
    monkeypatch.setattr(routes, "check_redis", lambda: CheckResult(ok=True, detail="reachable"))
    monkeypatch.setattr(routes, "check_storage", lambda deep=False: CheckResult(ok=True, detail="skipped"))

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "fail"
    assert body["checks"]["database"]["ok"] is False


def test_health_root_uses_readiness_semantics(monkeypatch) -> None:
    from app.health import routes
    from app.health.checks import CheckResult

    client = TestClient(app)
    monkeypatch.setattr(routes, "check_database", lambda: CheckResult(ok=True, detail="reachable"))
    monkeypatch.setattr(routes, "check_redis", lambda: CheckResult(ok=False, detail="redis unavailable"))
    monkeypatch.setattr(routes, "check_storage", lambda deep=False: CheckResult(ok=True, detail="skipped"))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "fail"


def test_readiness_optional_storage_deep_check(monkeypatch) -> None:
    from app.health import routes
    from app.health.checks import CheckResult

    client = TestClient(app)
    monkeypatch.setattr(routes, "check_database", lambda: CheckResult(ok=True, detail="reachable"))
    monkeypatch.setattr(routes, "check_redis", lambda: CheckResult(ok=True, detail="reachable"))

    observed = {"deep": False}

    def _check_storage(deep: bool = False) -> CheckResult:
        observed["deep"] = deep
        return CheckResult(ok=True, detail="ok")

    monkeypatch.setattr(routes, "check_storage", _check_storage)

    response = client.get("/health/ready?deep_storage=true")

    assert response.status_code == 200
    assert observed["deep"] is True
