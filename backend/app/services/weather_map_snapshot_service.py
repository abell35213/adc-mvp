"""Backward-compatible weather map snapshot service imports."""

from app.services.weather.map_snapshot_service import capture_weather_map_snapshot_if_missing

__all__ = ["capture_weather_map_snapshot_if_missing"]
