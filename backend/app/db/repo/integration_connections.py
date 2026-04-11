"""Repository layer for integration connections."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import IntegrationConnection


def create_integration_connection(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    domain: str | None = None,
    status: str = "pending",
    external_reference: str | None = None,
    credentials_ref: str | None = None,
    config_json: dict | None = None,
):
    connection = IntegrationConnection(
        org_id=org_id,
        provider=provider,
        domain=domain,
        status=status,
        external_reference=external_reference,
        credentials_ref=credentials_ref,
        config_json=config_json or {},
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def list_integration_connections(
    db: Session,
    org_id: _uuid.UUID | None = None,
    provider: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(IntegrationConnection)
    if org_id is not None:
        query = query.filter(IntegrationConnection.org_id == org_id)
    if provider is not None:
        query = query.filter(IntegrationConnection.provider == provider)
    if domain is not None:
        query = query.filter(IntegrationConnection.domain == domain)
    if status is not None:
        query = query.filter(IntegrationConnection.status == status)
    if external_reference is not None:
        query = query.filter(
            IntegrationConnection.external_reference == external_reference
        )
    return query.order_by(IntegrationConnection.created_at_utc.desc()).all()
