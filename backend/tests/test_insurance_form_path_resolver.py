"""Tests for the source-path resolver (plan test #9)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.crash_packet_query import CrashPacketRow
from app.services.insurance_form_path_resolver import (
    InvalidSourcePathError,
    parse_source_path,
    resolve_path,
    resolve_with_transform,
    row_to_root,
)


@pytest.fixture()
def root():
    return {
        "incident": {
            "incident_id": "abc-123",
            "adc_vehicle_id": "T-100",
            "severity": "serious",
        },
        "driver": {
            "display_name": "pat smith",
            "phone_e164": "+15551234567",
            "dob": "1985-04-12",
        },
        "vehicle": {"unit_number": "T-100", "vin": "1HGBH41JXMN109186"},
        "trailer": None,
        "maintenance": [
            {"vendor": "ShopA", "summary": "Brake check", "mileage": 100000},
            {"vendor": "ShopB", "summary": "Tire rotation"},
        ],
        "samsara_clip_links": [
            {"url": "https://example/1"},
            {"url": "https://example/2"},
        ],
    }


class TestParseSourcePath:
    def test_simple_two_segment(self):
        segs = parse_source_path("incident.adc_vehicle_id")
        assert [s.name for s in segs] == ["incident", "adc_vehicle_id"]
        assert all(s.index is None for s in segs)

    def test_indexed_segment(self):
        segs = parse_source_path("maintenance[0].vendor")
        assert segs[0].name == "maintenance" and segs[0].index == 0
        assert segs[1].name == "vendor" and segs[1].index is None

    def test_underscores_and_digits_in_identifier(self):
        segs = parse_source_path("driver_history.prior_count_2025")
        assert [s.name for s in segs] == ["driver_history", "prior_count_2025"]

    def test_empty_string_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path("")

    def test_non_string_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path(None)  # type: ignore[arg-type]

    def test_leading_digit_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path("9incident.x")

    def test_negative_index_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path("maintenance[-1].vendor")

    def test_double_index_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path("maintenance[0][1]")

    def test_dotted_into_index_rejected(self):
        with pytest.raises(InvalidSourcePathError):
            parse_source_path("a.[0]")


class TestResolvePath:
    def test_two_segment(self, root):
        assert resolve_path(root, "incident.adc_vehicle_id") == "T-100"

    def test_indexed(self, root):
        assert resolve_path(root, "maintenance[0].vendor") == "ShopA"
        assert resolve_path(root, "samsara_clip_links[1].url") == "https://example/2"

    def test_missing_key_returns_none(self, root):
        assert resolve_path(root, "incident.never_set") is None

    def test_missing_top_level_returns_none(self, root):
        assert resolve_path(root, "ghost.x.y") is None

    def test_index_past_end_returns_none(self, root):
        assert resolve_path(root, "maintenance[5].vendor") is None

    def test_index_into_non_list_returns_none(self, root):
        # ``incident`` is a dict, not a list — indexing must not raise.
        assert resolve_path(root, "incident[0].x") is None

    def test_dot_into_none_returns_none(self, root):
        # ``trailer`` is None in the fixture.
        assert resolve_path(root, "trailer.vin") is None

    def test_dot_into_scalar_returns_none(self, root):
        # ``incident.severity`` is a string; further segments must yield None.
        assert resolve_path(root, "incident.severity.upper") is None


class TestResolveWithTransform:
    def test_upper(self, root):
        assert resolve_with_transform(root, "driver.display_name", "upper") == (
            "PAT SMITH"
        )

    def test_date(self, root):
        result = resolve_with_transform(root, "driver.dob", "date")
        assert isinstance(result, datetime)
        assert result.year == 1985

    def test_none_value_skips_transform(self, root):
        # ``trailer`` resolves to None — transform never runs, no error.
        assert resolve_with_transform(root, "trailer.vin", "upper") is None


class TestRowToRoot:
    def test_strips_json_suffix_and_exposes_all_sections(self):
        row = CrashPacketRow(
            incident_json={"a": 1},
            driver_json={"name": "x"},
            driver_history_json=[{"id": "1"}],
            vehicle_json={"unit": "U"},
            trailer_json={"id": "TR"},
            maintenance_json=[{"v": "ShopA"}],
            eld_logs_json=[],
            samsara_clip_links_json=[{"url": "u"}],
            related_event_count=3,
        )
        root = row_to_root(row)
        assert root["incident"] == {"a": 1}
        assert root["driver"]["name"] == "x"
        assert root["driver_history"] == [{"id": "1"}]
        assert root["vehicle"]["unit"] == "U"
        assert root["trailer"]["id"] == "TR"
        assert root["maintenance"][0]["v"] == "ShopA"
        assert root["samsara_clip_links"][0]["url"] == "u"
        assert root["related_event_count"] == 3

    def test_round_trip_resolve_against_real_row(self):
        row = CrashPacketRow(
            incident_json={"adc_vehicle_id": "T-9"},
            driver_json=None,
            driver_history_json=[],
            vehicle_json=None,
            trailer_json=None,
            maintenance_json=[{"vendor": "Fast Lane"}],
            eld_logs_json=[],
            samsara_clip_links_json=[],
            related_event_count=0,
        )
        root = row_to_root(row)
        assert resolve_path(root, "incident.adc_vehicle_id") == "T-9"
        assert resolve_path(root, "maintenance[0].vendor") == "Fast Lane"
        assert resolve_path(root, "driver.display_name") is None  # driver is None
