from __future__ import annotations

from pathlib import Path


MANIFEST_PATH = Path(__file__).resolve().parents[2] / "infra/production/backend-deployment.yaml"


def _app_deployment_manifest() -> str:
    content = MANIFEST_PATH.read_text()
    first_doc = content.split("\n---\n", maxsplit=1)[0]
    return first_doc


def test_kubernetes_liveness_probe_matches_health_live_endpoint() -> None:
    manifest = _app_deployment_manifest()

    assert "livenessProbe:" in manifest
    assert "path: /health/live" in manifest


def test_kubernetes_readiness_probe_matches_health_ready_endpoint() -> None:
    manifest = _app_deployment_manifest()

    assert "readinessProbe:" in manifest
    assert "path: /health/ready" in manifest
