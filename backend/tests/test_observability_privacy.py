"""Privacy and suspicious-activity observability tests."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.observability.detection import AuditActivityDetector
from app.observability.logging import JsonFormatter
from app.observability.redaction import redact_payload_for_storage, redact_raw_payload


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


def test_raw_payload_redaction_masks_auth_and_otp():
    payload = "Authorization=Bearer abc123&otp_code=123456&note=driver%20said%20ok"
    redacted = redact_raw_payload(payload)
    assert "abc123" not in redacted
    assert "123456" not in redacted
    assert "driver%20said%20ok" not in redacted
    assert "%5BREDACTED%5D" in redacted
    assert "%5BREDACTED_OTP%5D" in redacted


def test_payload_storage_redaction_masks_nested_tokens():
    redacted = redact_payload_for_storage(
        {
            "Authorization": "Bearer token-value",
            "otp_code": "777888",
            "nested": {"api_key": "secret-key"},
        }
    )
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["otp_code"] == "[REDACTED_OTP]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
