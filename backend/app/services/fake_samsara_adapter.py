"""Fake Samsara adapter for local development and testing.

Returns canned JSON data from the ``examples/`` folder instead of
calling the real Samsara API.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


class FakeSamsaraAdapter:
    """Drop-in replacement for :class:`SamsaraClient` that serves fixture data."""

    def __init__(self, examples_dir: Path | None = None):
        self.examples_dir = examples_dir or EXAMPLES_DIR

    # ── helpers ────────────────────────────────────────────────────────

    def _load_json(self, filename: str) -> list:
        """Load a JSON file from the examples directory and return its data list."""
        path = self.examples_dir / filename
        if not path.exists():
            logger.warning("Example file not found: %s", path)
            return []
        with open(path) as f:
            return json.load(f).get("data", [])

    # ── public API (mirrors SamsaraClient) ─────────────────────────────

    def get_vehicle_locations(
        self, start: str | None = None, end: str | None = None
    ) -> list:
        """Return example vehicle location data."""
        return self._load_json("vehicle_locations.json")

    def get_safety_events(
        self, start: str | None = None, end: str | None = None
    ) -> list:
        """Return example safety events data."""
        return self._load_json("safety_events.json")

    def get_eld_logs(
        self, start: str | None = None, end: str | None = None
    ) -> list:
        """Return example ELD log data."""
        return self._load_json("eld_logs.json")

    def get_vehicle_state(
        self, start: str | None = None, end: str | None = None
    ) -> list:
        """Return example vehicle state data."""
        return self._load_json("vehicle_stats.json")

    def fetch_dashcam_stream(
        self,
        stream: str = "road_facing",
        start: str | None = None,
        end: str | None = None,
    ) -> bytes | None:
        """Return example dashcam bytes from the examples directory."""
        path = self.examples_dir / "dashcam_stream.bin"
        if not path.exists():
            return None
        return path.read_bytes()
