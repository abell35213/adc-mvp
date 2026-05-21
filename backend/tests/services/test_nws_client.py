from datetime import datetime, timedelta, timezone

import pytest

from app.services.weather.nws_client import InvalidWeatherWindowError, build_time_series_query


def test_build_time_series_query_option_b_window() -> None:
    incident_time = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    begin = incident_time - timedelta(hours=1)
    end = incident_time + timedelta(hours=1)

    params = build_time_series_query(lat=40.7128, lon=-74.006, begin=begin, end=end)

    assert params["begin"] == begin.isoformat()
    assert params["end"] == end.isoformat()


def test_build_time_series_query_includes_required_params() -> None:
    begin = datetime(2026, 1, 2, 11, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)

    params = build_time_series_query(lat=40.0, lon=-70.0, begin=begin, end=end)

    assert params["lat"] == "40.000000"
    assert params["lon"] == "-70.000000"
    assert params["product"] == "time-series"
    assert params["Unit"] == "e"
    for key in ("temp", "qpf", "snow", "wspd", "wdir", "wgust", "wwa", "iceaccum", "snowlvl", "vis"):
        assert params[key] == key


def test_build_time_series_query_accepts_equal_window() -> None:
    begin = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
    end = begin

    params = build_time_series_query(lat=1.0, lon=1.0, begin=begin, end=end)

    assert params["begin"] == params["end"]


def test_build_time_series_query_invalid_window_guard() -> None:
    begin = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, 11, 0, tzinfo=timezone.utc)

    with pytest.raises(InvalidWeatherWindowError, match="greater than or equal"):
        build_time_series_query(lat=1.0, lon=1.0, begin=begin, end=end)
