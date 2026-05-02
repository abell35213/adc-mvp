"""Unit tests for the FMCSA attribution matcher.

The matcher is a pure function over plain dataclasses, so we exercise:

* VIN-based and plate+state-based matching paths.
* Plate-only weak-strength match (state missing on one side).
* Inspection date inside vs. outside the unit-history window.
* Slip-seating across 3 tractors in 360 days.
* The confidence demotion table from §3 of the design doc.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.fmcsa_attribution import (
    InspectionRow,
    UnitHistoryRow,
    attribute_inspections,
)


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _unit(
    *,
    history_id: str = "u1",
    vin: str | None = None,
    license_plate: str | None = None,
    license_state: str | None = None,
    started: datetime,
    ended: datetime | None,
    confidence: str = "high",
    unit_kind: str = "tractor",
) -> UnitHistoryRow:
    return UnitHistoryRow(
        history_id=history_id,
        unit_kind=unit_kind,
        vin=vin,
        license_plate=license_plate,
        license_state=license_state,
        started_at_utc=started,
        ended_at_utc=ended,
        confidence=confidence,
    )


def _insp(
    *,
    inspection_id: str = "i1",
    insp_date: datetime,
    vin: str | None = None,
    plate: str | None = None,
    state: str | None = None,
) -> InspectionRow:
    return InspectionRow(
        inspection_id=inspection_id,
        inspection_date_utc=insp_date,
        vehicle_vin=vin,
        vehicle_license_plate=plate,
        vehicle_license_state=state,
    )


def test_vin_exact_match_high_unit_high_confidence_yields_high_match():
    units = [
        _unit(
            vin="1FUJGLDV6CSBR1234",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 6, 1),
            confidence="high",
        )
    ]
    inspections = [_insp(insp_date=_utc(2026, 3, 15), vin="1FUJGLDV6CSBR1234")]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
    m = matches[0]
    assert m.match_basis == "vin"
    assert m.match_confidence == "high"
    assert m.included_in_brief is True
    assert m.excluded_reason is None


def test_plate_state_match_high_unit_yields_high_match():
    units = [
        _unit(
            license_plate="ABC1234",
            license_state="TX",
            started=_utc(2026, 1, 1),
            ended=None,
            confidence="medium",  # open-ended assignment ⇒ medium
        )
    ]
    inspections = [
        _insp(insp_date=_utc(2026, 3, 15), plate="abc1234", state="tx")
    ]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
    assert matches[0].match_basis == "plate_state"
    # MEDIUM unit + STRONG vehicle → MEDIUM
    assert matches[0].match_confidence == "medium"
    assert matches[0].included_in_brief is True


def test_plate_only_match_with_high_unit_demotes_to_medium():
    units = [
        _unit(
            license_plate="ABC1234",
            license_state="TX",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 12, 31),
            confidence="high",
        )
    ]
    inspections = [
        _insp(insp_date=_utc(2026, 3, 15), plate="ABC1234", state=None)
    ]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
    # HIGH unit + WEAK vehicle → MEDIUM
    assert matches[0].match_confidence == "medium"
    assert matches[0].included_in_brief is True


def test_low_unit_with_strong_match_is_excluded():
    units = [
        _unit(
            vin="1FUJGLDV6CSBR1234",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 6, 1),
            confidence="low",
        )
    ]
    inspections = [_insp(insp_date=_utc(2026, 3, 15), vin="1FUJGLDV6CSBR1234")]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
    assert matches[0].match_confidence == "low"
    assert matches[0].included_in_brief is False
    assert "unit_history_confidence_low" in matches[0].excluded_reason


def test_inspection_outside_unit_window_is_not_matched():
    units = [
        _unit(
            vin="VIN1",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 2, 1),
            confidence="high",
        )
    ]
    inspections = [_insp(insp_date=_utc(2026, 5, 1), vin="VIN1")]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert matches == []


def test_slip_seating_three_tractors_in_360_days():
    units = [
        _unit(
            history_id="u-tractor-A",
            vin="VINA",
            started=_utc(2025, 5, 1),
            ended=_utc(2025, 8, 1),
            confidence="high",
        ),
        _unit(
            history_id="u-tractor-B",
            vin="VINB",
            started=_utc(2025, 8, 2),
            ended=_utc(2026, 1, 1),
            confidence="high",
        ),
        _unit(
            history_id="u-tractor-C",
            vin="VINC",
            started=_utc(2026, 1, 2),
            ended=None,
            confidence="medium",
        ),
    ]
    inspections = [
        _insp(inspection_id="iA", insp_date=_utc(2025, 6, 15), vin="VINA"),
        _insp(inspection_id="iB", insp_date=_utc(2025, 11, 1), vin="VINB"),
        _insp(inspection_id="iC", insp_date=_utc(2026, 3, 1), vin="VINC"),
        # An inspection on a tractor the driver was *never* in:
        _insp(inspection_id="iX", insp_date=_utc(2026, 2, 1), vin="OTHER"),
    ]
    matches = {m.inspection_id: m for m in attribute_inspections(
        inspections=inspections, unit_history=units
    )}
    assert set(matches) == {"iA", "iB", "iC"}
    assert matches["iA"].unit_history_id == "u-tractor-A"
    assert matches["iA"].match_confidence == "high"
    assert matches["iB"].unit_history_id == "u-tractor-B"
    assert matches["iC"].unit_history_id == "u-tractor-C"
    # Tractor C window is open-ended so unit confidence is MEDIUM,
    # vehicle is STRONG (VIN exact) → final = MEDIUM.
    assert matches["iC"].match_confidence == "medium"


def test_picks_higher_confidence_when_two_units_match_same_inspection():
    units = [
        _unit(
            history_id="u-low",
            vin="VIN1",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 12, 31),
            confidence="low",
        ),
        _unit(
            history_id="u-high",
            vin="VIN1",
            started=_utc(2026, 1, 1),
            ended=_utc(2026, 12, 31),
            confidence="high",
        ),
    ]
    inspections = [_insp(insp_date=_utc(2026, 3, 15), vin="VIN1")]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
    assert matches[0].unit_history_id == "u-high"
    assert matches[0].match_confidence == "high"


def test_inspection_with_no_matching_vehicle_is_dropped():
    units = [_unit(vin="VINA", started=_utc(2026, 1, 1), ended=None)]
    inspections = [_insp(insp_date=_utc(2026, 3, 15), vin="VINZ")]
    assert attribute_inspections(inspections=inspections, unit_history=units) == []


def test_naive_datetime_is_treated_as_utc():
    units = [
        _unit(
            vin="VIN1",
            started=datetime(2026, 1, 1),  # naive
            ended=datetime(2026, 12, 31),
            confidence="high",
        )
    ]
    inspections = [_insp(insp_date=datetime(2026, 3, 15), vin="VIN1")]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1


def test_empty_inputs_return_empty_list():
    assert attribute_inspections(inspections=[], unit_history=[]) == []


def test_inspection_with_no_date_is_dropped():
    units = [
        _unit(vin="VIN1", started=_utc(2026, 1, 1), ended=None, confidence="high")
    ]
    inspections = [_insp(insp_date=None, vin="VIN1")]
    assert attribute_inspections(inspections=inspections, unit_history=units) == []


def test_window_open_ended_includes_dates_after_start():
    units = [
        _unit(vin="VIN1", started=_utc(2026, 1, 1), ended=None, confidence="high")
    ]
    inspections = [
        _insp(insp_date=_utc(2026, 1, 1) + timedelta(days=400), vin="VIN1")
    ]
    matches = attribute_inspections(inspections=inspections, unit_history=units)
    assert len(matches) == 1
