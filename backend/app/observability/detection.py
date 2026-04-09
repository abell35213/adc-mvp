"""In-process suspicious activity detectors for high-signal audit events."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class DetectionAlert:
    rule: str
    severity: str
    message: str
    context: dict[str, Any]


class _SlidingWindowCounter:
    def __init__(self) -> None:
        self._events: dict[str, deque[datetime]] = defaultdict(deque)

    def increment_and_count(self, key: str, now: datetime, window: timedelta) -> int:
        bucket = self._events[key]
        bucket.append(now)
        cutoff = now - window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return len(bucket)


class AuditActivityDetector:
    """Applies threshold-based rules over recent audit events."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._auth_failures = _SlidingWindowCounter()
        self._admin_actions = _SlidingWindowCounter()
        self._downloads = _SlidingWindowCounter()

    def evaluate(
        self,
        *,
        org_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        event_type: str,
        outcome: str | None,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> list[DetectionAlert]:
        when = now or datetime.now(timezone.utc)
        details = metadata or {}
        alerts: list[DetectionAlert] = []

        with self._lock:
            if event_type == "auth_login_failed" or (action == "auth.login" and outcome == "failure"):
                count = self._auth_failures.increment_and_count(
                    key=f"{org_id}:{actor_id}", now=when, window=timedelta(minutes=10)
                )
                if count >= 5:
                    alerts.append(
                        DetectionAlert(
                            rule="repeated_auth_failures",
                            severity="high",
                            message="Repeated authentication failures detected",
                            context={"org_id": org_id, "actor_id": actor_id, "count": count, "window": "10m"},
                        )
                    )

            if action.startswith("admin."):
                count = self._admin_actions.increment_and_count(
                    key=f"{org_id}:{actor_id}", now=when, window=timedelta(minutes=5)
                )
                if outcome == "failure" or count >= 10:
                    alerts.append(
                        DetectionAlert(
                            rule="suspicious_admin_activity",
                            severity="high" if outcome == "failure" else "medium",
                            message="Suspicious admin activity detected",
                            context={
                                "org_id": org_id,
                                "actor_id": actor_id,
                                "action": action,
                                "outcome": outcome,
                                "count": count,
                                "window": "5m",
                            },
                        )
                    )

            if event_type == "export_downloaded" and action == "export.download" and outcome == "success":
                count = self._downloads.increment_and_count(
                    key=f"{org_id}:{actor_id}", now=when, window=timedelta(minutes=15)
                )
                if count >= 8:
                    alerts.append(
                        DetectionAlert(
                            rule="unusual_export_downloads",
                            severity="medium",
                            message="Unusual export download volume detected",
                            context={"org_id": org_id, "actor_id": actor_id, "count": count, "window": "15m"},
                        )
                    )

            if event_type == "authorization_failed" and action in {
                "export.authorize",
                "export.download",
                "export.request",
            }:
                alerts.append(
                    DetectionAlert(
                        rule="cross_org_access_attempt",
                        severity="high",
                        message="Potential cross-org access attempt detected",
                        context={
                            "org_id": org_id,
                            "actor_id": actor_id,
                            "action": action,
                            "resource": details.get("resource"),
                        },
                    )
                )

        return alerts


audit_activity_detector = AuditActivityDetector()
