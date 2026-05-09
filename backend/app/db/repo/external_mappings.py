"""Repository layer for external mappings."""

import uuid as _uuid

from sqlalchemy.orm import Session

from app.db.models import ExternalMapping


def create_external_mapping(
    db: Session,
    org_id: _uuid.UUID | None,
    provider: str,
    internal_entity_type: str,
    internal_entity_id: str,
    external_reference: str,
    incident_id: _uuid.UUID | None = None,
    domain: str | None = None,
    status: str = "active",
    metadata_json: dict | None = None,
):
    mapping = ExternalMapping(
        org_id=org_id,
        provider=provider,
        internal_entity_type=internal_entity_type,
        internal_entity_id=internal_entity_id,
        external_reference=external_reference,
        incident_id=incident_id,
        domain=domain,
        status=status,
        metadata_json=metadata_json or {},
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def list_external_mappings(
    db: Session,
    org_id: _uuid.UUID | None = None,
    incident_id: _uuid.UUID | None = None,
    status: str | None = None,
    provider: str | None = None,
    external_reference: str | None = None,
):
    query = db.query(ExternalMapping)
    if org_id is not None:
        query = query.filter(ExternalMapping.org_id == org_id)
    if incident_id is not None:
        query = query.filter(ExternalMapping.incident_id == incident_id)
    if status is not None:
        query = query.filter(ExternalMapping.status == status)
    if provider is not None:
        query = query.filter(ExternalMapping.provider == provider)
    if external_reference is not None:
        query = query.filter(ExternalMapping.external_reference == external_reference)
    return query.order_by(ExternalMapping.mapping_id.desc()).all()
