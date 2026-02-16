"""Basic test cases for the export API endpoints.

This module contains simple unit tests to exercise the new export
listing functionality. These tests are not exhaustive but
demonstrate how pytest can be used to drive the FastAPI app and
assert responses. To execute the tests, run ``pytest`` from the
repository root.

Note: In this exercise we do not spin up a real database or S3;
instead we rely on the default configuration of the app, which uses
an in-memory SQLite database when no external database is configured.
"""

import pytest
from fastapi.testclient import TestClient

# Attempt to import the FastAPI application. If the module is not available
# (e.g. the app has not been scaffolded in this environment), skip the tests.
try:
    from app.main import app  # type: ignore
except ModuleNotFoundError:
    pytest.skip("FastAPI app not available for testing", allow_module_level=True)


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient instance for the FastAPI app."""
    return TestClient(app)


def test_list_exports_empty(client: TestClient) -> None:
    """Ensure the list exports endpoint returns an empty list when no exports exist."""
    response = client.get("/api/exports")
    assert response.status_code == 200
    assert response.json() == []