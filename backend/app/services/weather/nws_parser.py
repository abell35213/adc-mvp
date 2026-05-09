"""Parser for NWS XML payloads into normalized weather data."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

FIELDS = ("temp", "qpf", "snow", "wspd", "wdir", "wgust", "wwa", "iceaccum", "snowlvl", "vis")


@dataclass(frozen=True)
class WeatherField:
    values: list[str]
    present: bool


def _extract_values(root: ElementTree.Element, field: str) -> list[str]:
    values: list[str] = []
    for node in root.findall(f".//{field}"):
        if node.text and node.text.strip():
            values.append(node.text.strip())
        for value_node in node.findall(".//value"):
            if value_node.text and value_node.text.strip():
                values.append(value_node.text.strip())
    return values


def parse_nws_time_series_xml(payload: str) -> dict[str, object]:
    """Return normalized weather payload plus explicit missing field metadata."""
    root = ElementTree.fromstring(payload)

    weather: dict[str, WeatherField] = {}
    missing_fields: list[str] = []
    for field in FIELDS:
        values = _extract_values(root, field)
        is_present = bool(values)
        weather[field] = WeatherField(values=values, present=is_present)
        if not is_present:
            missing_fields.append(field)

    normalized = {
        "weather": {name: {"values": field.values, "present": field.present} for name, field in weather.items()},
        "missing_fields": missing_fields,
        "is_partial": bool(missing_fields),
    }
    return normalized
