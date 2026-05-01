"""Dot-notation path resolver over a :class:`CrashPacketRow` (Phase 3).

A *source path* is the small grammar an operator types into the template
editor when mapping a form field to canonical data. It looks like::

    incident.adc_vehicle_id
    driver.dob
    vehicle.vin
    maintenance[0].vendor
    samsara_clip_links[1].url

Grammar (intentionally tiny):

* Segments are separated by ``.``
* A segment is either a ``[A-Za-z_][A-Za-z0-9_]*`` identifier or
  ``identifier[index]`` where ``index`` is a non-negative integer.
* Resolution starts at the *root dict* assembled from the canonical
  :class:`CrashPacketRow` (one top-level key per ``*_json`` field with the
  ``_json`` suffix stripped — see :func:`row_to_root`).
* Missing keys, missing list indices, or attempts to index a non-list
  return ``None`` rather than raising, so the renderer can mark the field
  empty (or, if ``required=True``, the fill service surfaces it on
  ``InsuranceFormFilling.missing_required_fields``).

``transform`` reuses the Phase-2 enumeration via
:func:`app.services.tms_odbc_connector.apply_transform`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.crash_packet_query import CrashPacketRow
from app.services.tms_odbc_connector import apply_transform

# An unindexed segment, optionally followed by a single ``[N]`` index.
_SEGMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")


class InvalidSourcePathError(ValueError):
    """Raised when ``source_path`` does not match the resolver grammar."""


@dataclass(frozen=True)
class _Segment:
    name: str
    index: int | None  # None if no [N] suffix


def parse_source_path(path: str) -> list[_Segment]:
    """Parse a source path into ordered segments.

    Validates the grammar up front so template-editor saves can fail loudly
    instead of silently mis-resolving at fill time.
    """
    if not isinstance(path, str) or not path.strip():
        raise InvalidSourcePathError("source_path must be a non-empty string")
    segments: list[_Segment] = []
    for raw in path.split("."):
        match = _SEGMENT_RE.match(raw.strip())
        if match is None:
            raise InvalidSourcePathError(f"Invalid segment in path: {raw!r}")
        name, idx = match.group(1), match.group(2)
        segments.append(_Segment(name=name, index=int(idx) if idx else None))
    return segments


def row_to_root(row: CrashPacketRow) -> dict[str, Any]:
    """Project a :class:`CrashPacketRow` onto the root dict source paths address.

    The ``_json`` suffix is stripped from each field so operators can write
    ``incident.x`` rather than ``incident_json.x``. ``related_event_count``
    is exposed at the root unchanged.
    """
    return {
        "incident": row.incident_json,
        "driver": row.driver_json,
        "driver_history": row.driver_history_json,
        "vehicle": row.vehicle_json,
        "trailer": row.trailer_json,
        "maintenance": row.maintenance_json,
        "eld_logs": row.eld_logs_json,
        "samsara_clip_links": row.samsara_clip_links_json,
        "related_event_count": row.related_event_count,
    }


def resolve_path(root: dict[str, Any], path: str) -> Any:
    """Walk ``path`` over ``root`` and return the value, or ``None`` if missing.

    * Indexing into a non-list returns ``None``.
    * Indexing past the end of a list returns ``None``.
    * Reaching ``None`` mid-walk returns ``None`` (downstream segments
      are not attempted).
    """
    segments = parse_source_path(path)
    current: Any = root
    for seg in segments:
        if current is None:
            return None
        if not isinstance(current, dict):
            # Cannot dot-into anything other than a dict.
            return None
        current = current.get(seg.name)
        if seg.index is not None:
            if not isinstance(current, list):
                return None
            if seg.index >= len(current):
                return None
            current = current[seg.index]
    return current


def resolve_with_transform(
    root: dict[str, Any], path: str, transform: str = "none"
) -> Any:
    """Resolve ``path`` and apply ``transform`` (Phase-2 grammar) to the result."""
    value = resolve_path(root, path)
    if value is None:
        return None
    return apply_transform(value, transform)
