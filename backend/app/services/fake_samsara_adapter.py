"""Backwards-compatible fake Samsara adapter wrapper."""

from __future__ import annotations

from pathlib import Path

from app.integrations.providers.fake_samsara import (
    SAMSARA_FIXTURES_DIR as _SAMSARA_FIXTURES_DIR,
    FakeSamsaraProvider,
)

SAMSARA_FIXTURES_DIR = _SAMSARA_FIXTURES_DIR


class FakeSamsaraAdapter:
    """Legacy API shim for tests; delegates to FakeSamsaraProvider."""

    def __init__(self, fixtures_dir: Path | None = None):
        self._provider = FakeSamsaraProvider(fixtures_dir=fixtures_dir)

    def get_vehicle_locations(self, start: str | None = None, end: str | None = None) -> list:
        return self._provider.fetch_gps_window(start=start, end=end)

    def get_safety_events(self, start: str | None = None, end: str | None = None) -> list:
        return self._provider.fetch_safety_events(start=start, end=end)

    def get_eld_logs(self, start: str | None = None, end: str | None = None) -> list:
        return self._provider.fetch_eld_window(start=start, end=end)

    def get_vehicle_state(self, start: str | None = None, end: str | None = None) -> list:
        return self._provider.fetch_vehicle_state(start=start, end=end)

    def fetch_dashcam_stream(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> bytes | None:
        clip_request_id = self._provider.request_clip(stream=stream, start=start, end=end)
        return self._provider.download_clip(clip_request_id)
