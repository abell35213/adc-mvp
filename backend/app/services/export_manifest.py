"""Export manifest generation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_export_manifest(
    *,
    options: dict[str, Any],
    included_files: list[str],
    missing_items: list[dict[str, str]],
    status_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "options": options,
        "included_files": sorted(included_files),
        "missing_items": missing_items,
        "status_metadata": status_metadata,
    }
