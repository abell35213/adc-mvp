from pathlib import Path

import pytest
from xml.etree.ElementTree import ParseError

from app.services.weather.nws_parser import FIELDS, parse_nws_time_series_xml

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "nws"


def _read_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_parse_nws_time_series_xml_full_fields() -> None:
    parsed = parse_nws_time_series_xml(_read_fixture("time_series_full.xml"))

    assert parsed["is_partial"] is False
    assert parsed["missing_fields"] == []
    assert set(parsed["weather"].keys()) == set(FIELDS)
    assert all(field["present"] is True for field in parsed["weather"].values())
    assert parsed["weather"]["temp"] == {"values": ["72", "73"], "present": True}
    assert parsed["weather"]["vis"] == {"values": ["10"], "present": True}


def test_parse_nws_time_series_xml_partial_fields() -> None:
    parsed = parse_nws_time_series_xml(_read_fixture("time_series_partial.xml"))

    assert set(parsed["weather"].keys()) == set(FIELDS)
    assert parsed["weather"]["temp"] == {"values": ["72"], "present": True}
    assert parsed["weather"]["qpf"] == {"values": ["0.1"], "present": True}
    assert parsed["weather"]["snow"] == {"values": [], "present": False}
    assert parsed["missing_fields"] == [
        "snow",
        "wdir",
        "wgust",
        "wwa",
        "iceaccum",
        "snowlvl",
        "vis",
    ]
    assert parsed["is_partial"] is True


def test_parse_nws_time_series_xml_malformed_payload_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_nws_time_series_xml(_read_fixture("time_series_malformed.xml"))
