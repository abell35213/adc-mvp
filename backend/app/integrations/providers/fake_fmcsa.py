"""Fixture-backed FMCSA provider for development/testing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FMCSA_FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "provider_fixtures"
    / "fmcsa"
)


class FakeFmcsaProvider:
    """Deterministic FMCSA provider for local + test environments."""

    def __init__(self, fixtures_dir: Path | None = None):
        self.fixtures_dir = fixtures_dir or FMCSA_FIXTURES_DIR

    def fetch_inspections(
        self,
        *,
        usdot_number: str,
        since: str,
        until: str,
    ) -> list[dict[str, Any]]:
        # Try a USDOT-specific fixture first, then the default.
        candidates = [
            self.fixtures_dir / f"inspections_{usdot_number}.json",
            self.fixtures_dir / "inspections.json",
        ]
        for path in candidates:
            if path.exists():
                with open(path) as fixture_file:
                    payload = json.load(fixture_file)
                if isinstance(payload, list):
                    return payload
                return payload.get("data", [])
        logger.warning(
            "No FMCSA fixture found for USDOT %s in %s", usdot_number, self.fixtures_dir
        )
        return []
