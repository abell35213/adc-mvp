from __future__ import annotations

import importlib.util
from email.message import Message
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / "scripts" / "verify_demo.py"
SPEC = importlib.util.spec_from_file_location("verify_demo", SCRIPT)
assert SPEC and SPEC.loader
verify_demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_demo)


@pytest.mark.parametrize(
    ("body", "content_type", "expected"),
    [
        ('{"ok": true}', "application/json", {"ok": True}),
        ('{"detail": "invalid"}', "application/problem+json", {"detail": "invalid"}),
        ("Internal Server Error", "text/plain; charset=utf-8", "Internal Server Error"),
        ("<html>Bad gateway</html>", "text/html", "<html>Bad gateway</html>"),
        ("", "application/json", None),
        ('{"broken":', "application/json", '{"broken":'),
        ('  [1, 2]', "text/plain", [1, 2]),
    ],
)
def test_response_parsing_is_content_type_aware(body, content_type, expected):
    assert verify_demo._parse_response_body(body, content_type) == expected


def test_body_preview_is_bounded():
    preview = verify_demo._safe_body_preview("x" * 800)
    assert len(preview) < 550
    assert preview.endswith("… [truncated]")


def test_error_diagnostic_exposes_only_safe_response_metadata():
    headers = Message()
    headers["X-Request-ID"] = "request-123"
    headers["Set-Cookie"] = "session=secret"
    headers["Authorization"] = "Bearer secret"
    message = verify_demo._unexpected_response_message(
        "GET", "/incidents/", 500, "text/plain", "Internal Server Error", headers
    )
    assert "GET /incidents/ returned 500" in message
    assert "Content-Type: text/plain" in message
    assert "Body: Internal Server Error" in message
    assert "Request ID: request-123" in message
    assert "secret" not in message


def test_bodyless_request_does_not_send_json_content_type(monkeypatch):
    captured = {}

    class Response:
        status = 200
        headers = Message()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b""

    client = verify_demo.ApiClient("http://example.test")

    def fake_open(request, timeout):
        captured["headers"] = dict(request.header_items())
        return Response()

    monkeypatch.setattr(client._opener, "open", fake_open)
    client.request("GET", "/health")
    lowered = {key.lower(): value for key, value in captured["headers"].items()}
    assert "content-type" not in lowered
    assert lowered["accept"] == "application/json"
