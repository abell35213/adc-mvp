"""Dashboard counters and aging metrics for case operations."""

from __future__ import annotations

from datetime import datetime, timezone

from app.case_ops.models import AgingMetrics, DashboardMetrics, CaseOpsSnapshot


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = max(0, min(len(sorted_values) - 1, round((percentile / 100) * (len(sorted_values) - 1))))
    return sorted_values[rank]


def calculate_dashboard_metrics(*, snapshots: list[CaseOpsSnapshot], created_at_values: list[datetime], now: datetime | None = None) -> DashboardMetrics:
    now_utc = now or datetime.now(timezone.utc)
    normalized_created_at_values = [
        created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
        for created_at in created_at_values
    ]
    ages_days = [
        max(0.0, (now_utc - created_at).total_seconds() / 86400.0)
        for created_at in normalized_created_at_values
    ]

    not_ready_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "not_ready")
    conditionally_ready_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "conditionally_ready")
    ready_for_export_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "ready_for_export")
    exported_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "exported")
    closed_cases = sum(1 for snapshot in snapshots if snapshot.readiness.state == "closed")

    return DashboardMetrics(
        total_open_cases=sum(1 for snapshot in snapshots if snapshot.readiness.state != "closed"),
        not_ready_cases=not_ready_cases,
        conditionally_ready_cases=conditionally_ready_cases,
        ready_for_export_cases=ready_for_export_cases,
        exported_cases=exported_cases,
        closed_cases=closed_cases,
        cases_with_critical_blockers=sum(1 for snapshot in snapshots if snapshot.blockers.critical_count > 0),
        cases_with_important_blockers=sum(1 for snapshot in snapshots if snapshot.blockers.important_count > 0),
        aging=AgingMetrics(
            average_age_days=(sum(ages_days) / len(ages_days)) if ages_days else 0.0,
            p95_age_days=_percentile(ages_days, 95),
            over_24h=sum(1 for age in ages_days if age >= 1),
            over_72h=sum(1 for age in ages_days if age >= 3),
            over_7d=sum(1 for age in ages_days if age >= 7),
        ),
    )
