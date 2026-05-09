"""NWS time-series query utilities and client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import httpx

from app.core.config import settings

BASE_URL = "https://forecast.weather.gov/MapClick.php"
WEATHER_ELEMENTS = "temp&qpf&snow&wspd&wdir&wgust&wwa&iceaccum&snowlvl&vis"


class InvalidWeatherWindowError(ValueError):
    """Raised when end timestamp occurs before begin timestamp."""


@dataclass(frozen=True)
class NWSQueryWindow:
    begin: datetime
    end: datetime


def build_time_series_query(
    *,
    lat: float,
    lon: float,
    begin: datetime,
    end: datetime,
    unit: str = "e",
) -> dict[str, str]:
    """Build query params for NWS time-series product endpoint."""
    if end < begin:
        raise InvalidWeatherWindowError("Weather query end must be greater than or equal to begin")

    return {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "product": "time-series",
        "begin": begin.isoformat(),
        "end": end.isoformat(),
        "Unit": unit,
        "temp": "temp",
        "qpf": "qpf",
        "snow": "snow",
        "wspd": "wspd",
        "wdir": "wdir",
        "wgust": "wgust",
        "wwa": "wwa",
        "iceaccum": "iceaccum",
        "snowlvl": "snowlvl",
        "vis": "vis",
    }


def build_time_series_url(*, lat: float, lon: float, begin: datetime, end: datetime) -> str:
    """Build full URL for the NWS time-series request."""
    params = build_time_series_query(lat=lat, lon=lon, begin=begin, end=end)
    return f"{BASE_URL}?{urlencode(params)}"


def fetch_nws_time_series_xml(*, lat: float, lon: float, begin: datetime, end: datetime) -> str:
    """Fetch NWS time-series XML using configured timeout/retry values."""
    timeout_seconds = float(getattr(settings, "NWS_REQUEST_TIMEOUT_SECONDS", 10.0))
    max_retries = int(getattr(settings, "NWS_REQUEST_MAX_RETRIES", 2))
    params = build_time_series_query(lat=lat, lon=lon, begin=begin, end=end)

    last_error: Exception | None = None
    for _attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(BASE_URL, params=params)
                response.raise_for_status()
                return response.text
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            last_error = exc

    assert last_error is not None
    raise last_error
