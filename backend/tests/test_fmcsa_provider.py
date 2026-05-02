"""Tests for the FMCSA provider (Socrata SoQL)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.providers.fake_fmcsa import FakeFmcsaProvider
from app.integrations.providers.fmcsa import FmcsaProvider


# ── Live provider (mocked transport) ────────────────────────────────


def _patch_httpx_transport(monkeypatch: pytest.MonkeyPatch, handler):
    """Make ``httpx.Client`` return a MockTransport built with ``handler``."""
    real_init = httpx.Client.__init__

    def _init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", _init)


def test_fetch_inspections_sends_soql_body_and_app_token(monkeypatch):
    captured: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=[])

    _patch_httpx_transport(monkeypatch, _handler)

    provider = FmcsaProvider(app_token="tok-123", base_url="https://example.test")
    rows = provider.fetch_inspections(
        usdot_number="12345678", since="2025-01-01", until="2026-01-01"
    )
    assert rows == []
    assert "fx4q-ay7w" in captured["url"]
    assert captured["headers"]["x-app-token"] == "tok-123"
    assert "12345678" in captured["body"]["query"]
    assert "2025-01-01" in captured["body"]["query"]
    assert "2026-01-01" in captured["body"]["query"]


def test_fetch_inspections_paginates_until_short_page(monkeypatch):
    pages = [
        # 1000 rows triggers another fetch
        [{"report_number": f"R{i}"} for i in range(1000)],
        # ... another full page
        [{"report_number": f"S{i}"} for i in range(1000)],
        # ... and finally a short page (terminates loop)
        [{"report_number": "T0"}],
    ]
    call_index = {"i": 0}

    def _handler(_request: httpx.Request) -> httpx.Response:
        page = pages[call_index["i"]]
        call_index["i"] += 1
        return httpx.Response(200, json=page)

    _patch_httpx_transport(monkeypatch, _handler)
    provider = FmcsaProvider(app_token="", base_url="https://example.test")
    rows = provider.fetch_inspections(
        usdot_number="123", since="2025-01-01", until="2026-01-01"
    )
    assert len(rows) == 2001
    assert call_index["i"] == 3


def test_fetch_inspections_empty_first_page_terminates(monkeypatch):
    calls = {"i": 0}

    def _handler(_request: httpx.Request) -> httpx.Response:
        calls["i"] += 1
        return httpx.Response(200, json=[])

    _patch_httpx_transport(monkeypatch, _handler)
    provider = FmcsaProvider(app_token="", base_url="https://example.test")
    rows = provider.fetch_inspections(
        usdot_number="0", since="2025-01-01", until="2026-01-01"
    )
    assert rows == []
    assert calls["i"] == 1


def test_rate_limit_429_raises_http_status_error(monkeypatch):
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate-limited"})

    _patch_httpx_transport(monkeypatch, _handler)
    provider = FmcsaProvider(app_token="t", base_url="https://example.test")
    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch_inspections(
            usdot_number="123", since="2025-01-01", until="2026-01-01"
        )


def test_server_error_raises_http_status_error(monkeypatch):
    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    _patch_httpx_transport(monkeypatch, _handler)
    provider = FmcsaProvider(app_token="t", base_url="https://example.test")
    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch_inspections(
            usdot_number="123", since="2025-01-01", until="2026-01-01"
        )


def test_no_app_token_omits_header(monkeypatch):
    captured: dict = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=[])

    _patch_httpx_transport(monkeypatch, _handler)
    provider = FmcsaProvider(app_token="", base_url="https://example.test")
    provider.fetch_inspections(
        usdot_number="0", since="2025-01-01", until="2026-01-01"
    )
    assert "x-app-token" not in {k.lower() for k in captured["headers"]}


# ── Fake provider ────────────────────────────────────────────────────


def test_fake_provider_returns_deterministic_fixture():
    provider = FakeFmcsaProvider()
    rows1 = provider.fetch_inspections(
        usdot_number="12345678", since="2025-01-01", until="2026-12-31"
    )
    rows2 = provider.fetch_inspections(
        usdot_number="12345678", since="2025-01-01", until="2026-12-31"
    )
    assert rows1 == rows2
    assert any(r.get("report_number", "").startswith("FAKE-") for r in rows1)


def test_fake_provider_returns_empty_when_no_fixture(tmp_path):
    provider = FakeFmcsaProvider(fixtures_dir=tmp_path)
    assert provider.fetch_inspections(
        usdot_number="999", since="2025-01-01", until="2026-12-31"
    ) == []
