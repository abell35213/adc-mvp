from pathlib import Path

import pytest

from app.services.weather.nws_parser import parse_nws_time_series_xml

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "nws"


def _read_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_parse_nws_time_series_xml_full_fields() -> None:
    parsed = parse_nws_time_series_xml(_read_fixture("time_series_full.xml"))

    assert parsed["is_partial"] is False
    assert parsed["missing_fields"] == []
    assert parsed["weather"]["temp"]["values"] == ["72", "73"]
    assert parsed["weather"]["vis"]["present"] is True


def test_parse_nws_time_series_xml_partial_fields() -> None:
    parsed = parse_nws_time_series_xml(_read_fixture("time_series_partial.xml"))

    assert parsed["weather"]["temp"]["present"] is True
    assert parsed["weather"]["temp"]["values"] == ["72"]
    assert parsed["weather"]["qpf"]["present"] is True
    assert parsed["weather"]["snow"]["present"] is False
    assert "snow" in parsed["missing_fields"]
    assert parsed["is_partial"] is True


def test_parse_nws_time_series_xml_malformed_payload_raises_parse_error() -> None:
    with pytest.raises(Exception):
        parse_nws_time_series_xml(_read_fixture("time_series_malformed.xml"))
