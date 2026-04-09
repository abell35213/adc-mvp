"""Privacy and suspicious-activity observability tests."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.observability.detection import AuditActivityDetector
from app.observability.logging import JsonFormatter


def _format_log(message: str, **extra) -> dict:
    logger = logging.getLogger("privacy-test")
    record = logger.makeRecord(
        name="privacy-test",
        level=logging.INFO,
        fn=__file__,
        lno=10,
        msg=message,
        args=(),
        exc_info=None,
        extra=extra,
    )
    rendered = JsonFormatter().format(record)
    return json.loads(rendered)


def test_generic_logs_redact_sensitive_class_a_values():
    payload = _format_log(
        "Authorization: Bearer super.secret.token password=hunter2",
        user_id="u-1",
        path="/auth/login",
    )

    assert "super.secret.token" not in payload["message"]
    assert "hunter2" not in payload["message"]
    assert "[REDACTED]" in payload["message"]


def test_generic_logs_redact_sensitive_class_b_values():
    payload = _format_log(
        "otp_code=123456 note=driver admitted fault",
        method="POST",
        status_code=401,
    )

    assert "123456" not in payload["message"]
    assert "driver admitted fault" not in payload["message"]
    assert "[REDACTED_OTP]" in payload["message"]
    assert "[REDACTED_NOTE]" in payload["message"]


def test_detection_rules_cover_expected_suspicious_behaviors():
    detector = AuditActivityDetector()
    org_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    alerts = []
    for offset in range(5):
        alerts.extend(
            detector.evaluate(
                org_id=org_id,
                actor_type="user",
                actor_id="user-1",
                action="auth.login",
                event_type="auth_login_failed",
                outcome="failure",
                now=now + timedelta(minutes=offset),
            )
        )
    assert any(a.rule == "repeated_auth_failures" for a in alerts)

    admin_alerts = detector.evaluate(
        org_id=org_id,
        actor_type="user",
        actor_id="admin-1",
        action="admin.vehicle_qr.rotate",
        event_type="authorization_failed",
        outcome="failure",
        now=now,
    )
    assert any(a.rule == "suspicious_admin_activity" for a in admin_alerts)

    export_alerts = []
    for offset in range(8):
        export_alerts.extend(
            detector.evaluate(
                org_id=org_id,
                actor_type="user",
                actor_id="user-2",
                action="export.download",
                event_type="export_downloaded",
                outcome="success",
                now=now + timedelta(minutes=offset),
            )
        )
    assert any(a.rule == "unusual_export_downloads" for a in export_alerts)

    cross_org_alerts = detector.evaluate(
        org_id=org_id,
        actor_type="user",
        actor_id="user-3",
        action="export.download",
        event_type="authorization_failed",
        outcome="failure",
        metadata={"resource": "export_download"},
        now=now,
    )
    assert any(a.rule == "cross_org_access_attempt" for a in cross_org_alerts)
