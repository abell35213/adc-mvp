"""Fixture-backed Samsara provider for development/testing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SAMSARA_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "provider_fixtures" / "samsara"
)


class FakeSamsaraProvider:
    def __init__(self, fixtures_dir: Path | None = None):
        self.fixtures_dir = fixtures_dir or SAMSARA_FIXTURES_DIR
        self._clip_requests: dict[str, dict[str, str | None]] = {}

    def _load_json(self, filename: str) -> list[dict[str, Any]]:
        path = self.fixtures_dir / filename
        if not path.exists():
            logger.warning("Fixture file not found: %s", path)
            return []
        with open(path) as fixture_file:
            return json.load(fixture_file).get("data", [])

    def fetch_gps_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._load_json("vehicle_locations.json")

    def fetch_eld_window(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._load_json("eld_logs.json")

    def fetch_vehicle_state(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._load_json("vehicle_stats.json")

    def fetch_safety_events(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        return self._load_json("safety_events.json")

    def request_clip(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        clip_id = f"fake-{stream}-{start or 'none'}-{end or 'none'}"
        self._clip_requests[clip_id] = {"stream": stream, "start": start, "end": end}
        return clip_id

    def fetch_clip_status(self, clip_request_id: str) -> dict[str, Any]:
        if clip_request_id not in self._clip_requests:
            return {"status": "not_found"}
        return {"status": "ready", "clip_request_id": clip_request_id}

    def download_clip(self, clip_request_id: str) -> bytes | None:
        if clip_request_id not in self._clip_requests:
            return None
        path = self.fixtures_dir / "dashcam_stream.bin"
        if not path.exists():
            return None
        return path.read_bytes()
