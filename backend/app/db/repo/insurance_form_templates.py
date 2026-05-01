"""Repository for insurance_form_templates (Phase 3)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import InsuranceFormTemplate, InsuranceFormTemplateField


def create_template(
    db: Session,
    *,
    org_id: _uuid.UUID,
    name: str,
    carrier: str | None = None,
    s3_bucket: str | None = None,
    s3_key: str | None = None,
    sha256: str | None = None,
    page_count: int | None = None,
    created_by_user_id: _uuid.UUID | None = None,
) -> InsuranceFormTemplate:
    """Create a new ``draft`` template at version 1 for ``(org_id, name)``.

    If a template with the same ``(org_id, name)`` already exists the new
    template is created at ``max(version) + 1``.
    """
    latest_version = (
        db.query(InsuranceFormTemplate.version)
        .filter(
            InsuranceFormTemplate.org_id == org_id,
            InsuranceFormTemplate.name == name,
        )
        .order_by(InsuranceFormTemplate.version.desc())
        .first()
    )
    next_version = (latest_version[0] + 1) if latest_version else 1

    template = InsuranceFormTemplate(
        org_id=org_id,
        name=name,
        carrier=carrier,
        version=next_version,
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        sha256=sha256,
        page_count=page_count,
        created_by_user_id=created_by_user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(
    db: Session, template_id: _uuid.UUID
) -> InsuranceFormTemplate | None:
    return (
        db.query(InsuranceFormTemplate)
        .filter(InsuranceFormTemplate.id == template_id)
        .first()
    )


def list_org_templates(
    db: Session, org_id: _uuid.UUID
) -> list[InsuranceFormTemplate]:
    return (
        db.query(InsuranceFormTemplate)
        .filter(InsuranceFormTemplate.org_id == org_id)
        .order_by(
            InsuranceFormTemplate.name, InsuranceFormTemplate.version.desc()
        )
        .all()
    )


def list_template_fields(
    db: Session, template_id: _uuid.UUID
) -> list[InsuranceFormTemplateField]:
    return (
        db.query(InsuranceFormTemplateField)
        .filter(InsuranceFormTemplateField.template_id == template_id)
        .order_by(
            InsuranceFormTemplateField.sort_order,
            InsuranceFormTemplateField.name,
        )
        .all()
    )


def mark_finalized(
    db: Session, template: InsuranceFormTemplate
) -> InsuranceFormTemplate:
    template.status = "finalized"
    template.finalized_at_utc = datetime.now(timezone.utc)
    db.commit()
    db.refresh(template)
    return template
