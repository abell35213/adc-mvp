"""Tests for ``app.integrations.normalization`` value objects and helpers.

Covers the dataclass defaults / immutability and the ``parse_iso_datetime``
and ``as_list`` helpers, including the boundary cases that are easy to get
wrong (``None``, empty string, trailing ``Z`` suffix, non-list payloads, and
filtering of non-dict rows).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.integrations.normalization import (
    ClipRequest,
    StoredFile,
    TimeWindow,
    as_list,
    parse_iso_datetime,
)


class TestTimeWindow:
    def test_defaults_are_none(self) -> None:
        window = TimeWindow()
        assert window.start is None
        assert window.end is None

    def test_explicit_values_round_trip(self) -> None:
        window = TimeWindow(start="2024-01-01T00:00:00Z", end="2024-01-02T00:00:00Z")
        assert window.start == "2024-01-01T00:00:00Z"
        assert window.end == "2024-01-02T00:00:00Z"

    def test_is_frozen(self) -> None:
        window = TimeWindow()
        with pytest.raises(FrozenInstanceError):
            window.start = "later"  # type: ignore[misc]


class TestClipRequest:
    def test_default_stream_is_road_facing(self) -> None:
        req = ClipRequest()
        assert req.stream == "road_facing"
        assert req.start is None
        assert req.end is None

    def test_custom_stream(self) -> None:
        req = ClipRequest(stream="driver_facing", start="2024-01-01T00:00:00Z")
        assert req.stream == "driver_facing"
        assert req.start == "2024-01-01T00:00:00Z"


class TestStoredFile:
    def test_required_key_only(self) -> None:
        sf = StoredFile(key="bucket/object")
        assert sf.key == "bucket/object"
        assert sf.content_type is None
        assert sf.byte_size is None

    def test_full_metadata(self) -> None:
        sf = StoredFile(key="a/b", content_type="application/pdf", byte_size=2048)
        assert sf.content_type == "application/pdf"
        assert sf.byte_size == 2048


class TestParseIsoDatetime:
    def test_returns_none_for_none(self) -> None:
        assert parse_iso_datetime(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        # falsy strings should also short-circuit; this protects callers
        # from passing in empty provider responses.
        assert parse_iso_datetime("") is None

    def test_parses_offset_naive_iso(self) -> None:
        result = parse_iso_datetime("2024-05-06T07:08:09")
        assert result == datetime(2024, 5, 6, 7, 8, 9)

    def test_parses_z_suffix_as_utc(self) -> None:
        result = parse_iso_datetime("2024-05-06T07:08:09Z")
        assert result == datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)

    def test_parses_offset_aware_iso(self) -> None:
        result = parse_iso_datetime("2024-05-06T07:08:09+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_iso_datetime("not-a-date")


class TestAsList:
    def test_none_returns_empty_list(self) -> None:
        assert as_list(None) == []

    def test_empty_list_returns_empty(self) -> None:
        assert as_list([]) == []

    def test_filters_non_dict_entries(self) -> None:
        payload = [{"a": 1}, "skip", 42, None, {"b": 2}]
        assert as_list(payload) == [{"a": 1}, {"b": 2}]

    def test_passes_through_dict_list(self) -> None:
        payload = [{"x": 1}, {"y": 2}]
        assert as_list(payload) == payload

    @pytest.mark.parametrize("payload", [{}, "string", 5, 5.0, True, object()])
    def test_non_list_payload_raises(self, payload: object) -> None:
        with pytest.raises(ValueError, match="Expected list payload"):
            as_list(payload)
