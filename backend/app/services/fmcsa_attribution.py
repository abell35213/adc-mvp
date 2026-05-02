"""Pure-function FMCSA inspection ↔ driver-unit-history attribution.

Implements the slip-seating attribution policy from the design doc.

Inputs are plain dicts/dataclasses (not ORM rows) so this module is
trivial to unit test and can be reused from both the Celery task and
the re-poll beat job.

Confidence rules
----------------
``unit_history.confidence`` (string ``high|medium|low``) reflects how
well we trust that the driver was actually in this unit at the
``[started_at_utc, ended_at_utc]`` window — see
``driver_violation_history_capture_service`` for how it's assigned.

A vehicle match strength is derived from the FMCSA inspection ↔ unit
identifiers:

* ``strong``   — VIN exact, OR (license_plate, license_state) exact.
* ``weak``     — license_plate-only match (state missing on either side).

The final ``match_confidence`` for an
``incident_driver_violation_history`` row is:

* both unit_history HIGH + match strong → ``high``
* unit_history MEDIUM + match strong, OR HIGH + match weak → ``medium``
* otherwise → ``low`` (stored, but ``included_in_brief = False``)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal, Optional

UnitConfidence = Literal["high", "medium", "low"]
MatchBasis = Literal["vin", "plate_state"]
MatchConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class UnitHistoryRow:
    """A snapshot of one ``driver_unit_history`` row used by the matcher."""

    history_id: str
    unit_kind: str  # "tractor" | "trailer"
    vin: Optional[str]
    license_plate: Optional[str]
    license_state: Optional[str]
    started_at_utc: datetime
    ended_at_utc: Optional[datetime]
    confidence: UnitConfidence


@dataclass(frozen=True)
class InspectionRow:
    """A snapshot of one ``fmcsa_inspections`` row used by the matcher."""

    inspection_id: str
    inspection_date_utc: Optional[datetime]
    vehicle_vin: Optional[str]
    vehicle_license_plate: Optional[str]
    vehicle_license_state: Optional[str]


@dataclass(frozen=True)
class AttributionMatch:
    """The matcher output: enough metadata to write the link table row."""

    inspection_id: str
    unit_history_id: str
    match_basis: MatchBasis
    match_confidence: MatchConfidence
    included_in_brief: bool
    excluded_reason: Optional[str]


def _norm(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _within_window(
    inspection_date: Optional[datetime],
    started: datetime,
    ended: Optional[datetime],
) -> bool:
    insp = _aware(inspection_date)
    if insp is None:
        return False
    start_aw = _aware(started)
    if start_aw is not None and insp < start_aw:
        return False
    end_aw = _aware(ended)
    if end_aw is not None and insp > end_aw:
        return False
    return True


def _vehicle_match(
    inspection: InspectionRow, unit: UnitHistoryRow
) -> Optional[tuple[MatchBasis, str]]:
    """Return ``(basis, strength)`` if the inspection's vehicle ids match the
    unit's, otherwise ``None``. ``strength`` is ``"strong"`` or ``"weak"``.
    """
    insp_vin = _norm(inspection.vehicle_vin)
    unit_vin = _norm(unit.vin)
    if insp_vin and unit_vin and insp_vin == unit_vin:
        return ("vin", "strong")

    insp_plate = _norm(inspection.vehicle_license_plate)
    unit_plate = _norm(unit.license_plate)
    if insp_plate and unit_plate and insp_plate == unit_plate:
        insp_state = _norm(inspection.vehicle_license_state)
        unit_state = _norm(unit.license_state)
        if insp_state and unit_state and insp_state == unit_state:
            return ("plate_state", "strong")
        # Plate matched but state missing on one side → weak.
        return ("plate_state", "weak")

    return None


def _final_confidence(
    unit_confidence: UnitConfidence, vehicle_strength: str
) -> MatchConfidence:
    if unit_confidence == "high" and vehicle_strength == "strong":
        return "high"
    if unit_confidence == "medium" and vehicle_strength == "strong":
        return "medium"
    if unit_confidence == "high" and vehicle_strength == "weak":
        return "medium"
    return "low"


def _excluded_reason(
    final: MatchConfidence,
    unit_confidence: UnitConfidence,
    vehicle_strength: str,
) -> Optional[str]:
    if final in ("high", "medium"):
        return None
    parts = []
    if unit_confidence == "low":
        parts.append("unit_history_confidence_low")
    if vehicle_strength == "weak":
        parts.append("vehicle_match_weak")
    if not parts:
        parts.append("insufficient_confidence")
    return ",".join(parts)


def attribute_inspections(
    *,
    inspections: Iterable[InspectionRow],
    unit_history: Iterable[UnitHistoryRow],
) -> list[AttributionMatch]:
    """Match a set of FMCSA inspections against a driver's unit history.

    Returns one :class:`AttributionMatch` per matched ``(inspection, unit)``
    pair. Multiple unit-history rows can match the same inspection (e.g.
    overlapping records); the caller is responsible for de-duplicating
    by ``inspection_id`` (we use a unique index ``(incident_id,
    inspection_id)`` and pick the highest-confidence match).
    """
    units = list(unit_history)
    out: list[AttributionMatch] = []
    seen_best: dict[str, AttributionMatch] = {}

    confidence_rank = {"high": 2, "medium": 1, "low": 0}

    for inspection in inspections:
        for unit in units:
            if not _within_window(
                inspection.inspection_date_utc,
                unit.started_at_utc,
                unit.ended_at_utc,
            ):
                continue
            vehicle = _vehicle_match(inspection, unit)
            if vehicle is None:
                continue
            basis, strength = vehicle
            final = _final_confidence(unit.confidence, strength)
            included = final in ("high", "medium")
            match = AttributionMatch(
                inspection_id=inspection.inspection_id,
                unit_history_id=unit.history_id,
                match_basis=basis,
                match_confidence=final,
                included_in_brief=included,
                excluded_reason=_excluded_reason(final, unit.confidence, strength),
            )
            existing = seen_best.get(inspection.inspection_id)
            if (
                existing is None
                or confidence_rank[match.match_confidence]
                > confidence_rank[existing.match_confidence]
            ):
                seen_best[inspection.inspection_id] = match

    out = list(seen_best.values())
    return out
