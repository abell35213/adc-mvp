"""Export manifest generation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_export_manifest(
    *,
    options: dict[str, Any],
    profile_id: str,
    required_sections: list[str],
    optional_sections: list[str],
    summary_style: str,
    included_files: list[str],
    file_manifest: list[dict[str, Any]],
    missing_items: list[dict[str, str]],
    status_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile_id": profile_id,
        "required_sections": required_sections,
        "optional_sections": optional_sections,
        "summary_style": summary_style,
        "options": options,
        "included_files": sorted(included_files),
        "file_manifest": file_manifest,
        "missing_items": missing_items,
        "status_metadata": status_metadata,
    }
