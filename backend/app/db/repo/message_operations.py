"""Repository layer for message operations."""

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.models import MessageOperation, MessageOperationStatusHistory


def create_message_operation(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    status: str = "queued",
    incident_id: _uuid.UUID | None = None,
    operation_id: _uuid.UUID | None = None,
    domain: str | None = None,
    purpose: str = "notification",
    to_e164: str | None = None,
    provider_message_id: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
    normalized_error_code: str | None = None,
    payload_json: dict | None = None,
):
    message_operation = MessageOperation(
        org_id=org_id,
        provider=provider,
        status=status,
        incident_id=incident_id,
        operation_id=operation_id,
        purpose=purpose,
        to_e164=to_e164,
        provider_message_id=provider_message_id,
        normalized_error_code=normalized_error_code,
        domain=domain,
        correlation_id=correlation_id,
        external_reference=external_reference,
        payload_json=payload_json or {},
    )
    db.add(message_operation)
    db.flush()
    db.add(
        MessageOperationStatusHistory(
            message_operation_id=message_operation.message_operation_id,
            from_status=None,
            to_status=status,
            provider_message_id=provider_message_id,
            normalized_error_code=normalized_error_code,
            details_json={},
        )
    )
    db.commit()
    db.refresh(message_operation)
    return message_operation


def update_message_operation_status(
    db: Session,
    message_operation: MessageOperation,
    *,
    to_status: str,
    provider_message_id: str | None = None,
    normalized_error_code: str | None = None,
    details_json: dict | None = None,
) -> MessageOperation:
    from_status = message_operation.status
    message_operation.status = to_status
    if provider_message_id:
        message_operation.provider_message_id = provider_message_id
    if normalized_error_code is not None:
        message_operation.normalized_error_code = normalized_error_code
    now = datetime.now(timezone.utc)
    if to_status == "sent":
        message_operation.sent_at_utc = now
    if to_status in {"delivered", "undelivered", "failed"}:
        message_operation.delivered_at_utc = now
    db.add(
        MessageOperationStatusHistory(
            message_operation_id=message_operation.message_operation_id,
            from_status=from_status,
            to_status=to_status,
            provider_message_id=provider_message_id or message_operation.provider_message_id,
            normalized_error_code=normalized_error_code,
            details_json=details_json or {},
        )
    )
    db.commit()
    db.refresh(message_operation)
    return message_operation


def get_message_operation_by_provider_message_id(
    db: Session,
    *,
    provider: str,
    provider_message_id: str,
) -> MessageOperation | None:
    return (
        db.query(MessageOperation)
        .filter(
            MessageOperation.provider == provider,
            MessageOperation.provider_message_id == provider_message_id,
        )
        .order_by(MessageOperation.created_at_utc.desc())
        .first()
    )


def get_messaging_reliability_summary(
    db: Session,
    *,
    org_id: _uuid.UUID,
    incident_id: _uuid.UUID | None = None,
) -> dict[str, int]:
    query = db.query(
        func.count(MessageOperation.message_operation_id).label("total"),
        func.sum(case((MessageOperation.status == "delivered", 1), else_=0)).label("delivered"),
        func.sum(case((MessageOperation.status == "undelivered", 1), else_=0)).label("undelivered"),
        func.sum(case((MessageOperation.status == "failed", 1), else_=0)).label("failed"),
    ).filter(MessageOperation.org_id == org_id)
    if incident_id is not None:
        query = query.filter(MessageOperation.incident_id == incident_id)
    row = query.one()
    total = int(row.total or 0)
    delivered = int(row.delivered or 0)
    undelivered = int(row.undelivered or 0)
    failed = int(row.failed or 0)
    return {
        "total": total,
        "delivered": delivered,
        "undelivered": undelivered,
        "failed": failed,
        "success_rate_pct": int(round((delivered / total) * 100)) if total else 0,
    }


def list_message_operations(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    correlation_id: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(MessageOperation)
    if org_id is not None:
        query = query.filter(MessageOperation.org_id == org_id)
    if incident_id is not None:
        query = query.filter(MessageOperation.incident_id == incident_id)
    if status is not None:
        query = query.filter(MessageOperation.status == status)
    if provider is not None:
        query = query.filter(MessageOperation.provider == provider)
    if correlation_id is not None:
        query = query.filter(MessageOperation.correlation_id == correlation_id)
    if external_reference is not None:
        query = query.filter(MessageOperation.external_reference == external_reference)
    return query.order_by(MessageOperation.created_at_utc.desc()).all()
