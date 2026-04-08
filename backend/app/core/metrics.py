"""Backward-compatible metrics imports."""

from app.observability.metrics import MetricNames, increment, timed

__all__ = ["MetricNames", "increment", "timed"]
