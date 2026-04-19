"""Reporting feature gates keyed by canonical feature ids."""

from __future__ import annotations

REPORTING_FEATURES: tuple[str, ...] = (
    "reporting.dashboard",
    "reporting.audit_trail",
    "reporting.export_history",
)
