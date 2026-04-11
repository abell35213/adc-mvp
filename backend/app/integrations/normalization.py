"""Integration normalization helpers and common value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TimeWindow:
    """Time window passed to integration providers."""

    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class ClipRequest:
    """Dashcam clip request parameters."""

    stream: str = "road_facing"
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class StoredFile:
    """Metadata for persisted files."""

    key: str
    content_type: str | None = None
    byte_size: int | None = None


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def as_list(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected list payload, got {type(payload).__name__}")
