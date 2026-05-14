"""Insurance form template editor service (Phase 3).

Operators land here after uploading a blank form. They:

1. (optionally) ingest detected fields from
   :mod:`insurance_form_ocr` via :func:`ingest_detected_fields`.
2. Add / edit / remove fields via :func:`add_field`, :func:`update_field`,
   :func:`remove_field`. ``source_path`` is validated up front via the
   Phase-3 path resolver — no editor save can persist a malformed path.
3. Call :func:`finalize_template` once the field map is complete. After
   finalize, attempts to mutate fields raise :class:`TemplateLockedError`
   and the template must be cloned via :func:`clone_for_edit` (which
   creates a new draft version).
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from typing import Any, Iterable, cast

from sqlalchemy.orm import Session

from app.db.models import InsuranceFormTemplate, InsuranceFormTemplateField
from app.db.repo import insurance_form_templates as repo
from app.services.insurance_form_ocr import DetectedField
from app.services.insurance_form_path_resolver import parse_source_path
from app.services.tms_odbc_connector import (
    UnknownTransformError,
    apply_transform,
)


class TemplateLockedError(RuntimeError):
    """Raised when an edit is attempted on a finalized template."""


class TemplateNotReadyError(ValueError):
    """Raised when finalize is called but required preconditions aren't met."""


@dataclass(frozen=True)
class FieldSpec:
    """Editor input for one field. ``name`` is the unique key per template."""

    name: str
    label: str | None = None
    page: int | None = None
    kind: str = "text"
    bbox: dict | None = None
    source_path: str | None = None
    transform: str = "none"
    required: bool = False
    default_value: str | None = None
    sort_order: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────


_VALID_KINDS = frozenset({"text", "date", "checkbox", "signature"})


def _ensure_draft(template: InsuranceFormTemplate) -> None:
    if template.status != "draft":
        raise TemplateLockedError(
            f"Template {template.id} is {template.status}; clone for edit first"
        )


def _validate_spec(spec: FieldSpec) -> None:
    if not spec.name or not spec.name.strip():
        raise ValueError("FieldSpec.name is required")
    if spec.kind not in _VALID_KINDS:
        raise ValueError(f"Invalid field kind: {spec.kind!r}")
    if spec.source_path is not None:
        # Raises InvalidSourcePathError on grammar errors.
        parse_source_path(spec.source_path)
    # Validate transform by exercising it on a sentinel value.
    try:
        apply_transform("sentinel", spec.transform)
    except UnknownTransformError as exc:
        # Re-raise as ValueError for a uniform editor-side error.
        raise ValueError(str(exc)) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def add_field(
    db: Session,
    *,
    template_id: _uuid.UUID,
    spec: FieldSpec,
) -> InsuranceFormTemplateField:
    """Append a new field to a draft template."""
    template = repo.get_template(db, template_id)
    if template is None:
        raise LookupError(f"Template {template_id} not found")
    _ensure_draft(template)
    _validate_spec(spec)

    field = InsuranceFormTemplateField(
        template_id=template_id,
        name=spec.name.strip(),
        label=spec.label,
        page=spec.page,
        kind=spec.kind,
        bbox_json=spec.bbox,
        source_path=spec.source_path,
        transform=spec.transform,
        required=spec.required,
        default_value=spec.default_value,
        sort_order=spec.sort_order,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def update_field(
    db: Session,
    *,
    field_id: _uuid.UUID,
    changes: dict[str, Any],
) -> InsuranceFormTemplateField:
    """Apply partial changes to a draft template's field."""
    field = (
        db.query(InsuranceFormTemplateField)
        .filter(InsuranceFormTemplateField.id == field_id)
        .first()
    )
    if field is None:
        raise LookupError(f"Field {field_id} not found")
    field_row = cast(Any, field)
    template = repo.get_template(db, cast(_uuid.UUID, field_row.template_id))
    if template is None:
        raise LookupError(f"Template {field.template_id} not found")
    _ensure_draft(template)

    # Build a tentative spec from the merged values and validate.
    merged = FieldSpec(
        name=str(changes.get("name", field.name)),
        label=changes.get("label", field.label),
        page=changes.get("page", field.page),
        kind=str(changes.get("kind", field.kind)),
        bbox=changes.get("bbox", field.bbox_json),
        source_path=changes.get("source_path", field.source_path),
        transform=str(changes.get("transform", field.transform)),
        required=bool(changes.get("required", field.required)),
        default_value=changes.get("default_value", field.default_value),
        sort_order=int(changes.get("sort_order", field.sort_order)),
    )
    _validate_spec(merged)

    field_row.name = merged.name
    field_row.label = merged.label
    field_row.page = merged.page
    field_row.kind = merged.kind
    field_row.bbox_json = merged.bbox
    field_row.source_path = merged.source_path
    field_row.transform = merged.transform
    field_row.required = merged.required
    field_row.default_value = merged.default_value
    field_row.sort_order = merged.sort_order
    db.commit()
    db.refresh(field)
    return field


def remove_field(db: Session, *, field_id: _uuid.UUID) -> None:
    field = (
        db.query(InsuranceFormTemplateField)
        .filter(InsuranceFormTemplateField.id == field_id)
        .first()
    )
    if field is None:
        return
    template = repo.get_template(db, cast(_uuid.UUID, cast(Any, field).template_id))
    if template is not None:
        _ensure_draft(template)
    db.delete(field)
    db.commit()


def ingest_detected_fields(
    db: Session,
    *,
    template_id: _uuid.UUID,
    detected: Iterable[DetectedField],
) -> list[InsuranceFormTemplateField]:
    """Bulk-create draft fields from a :class:`DetectionResult`.

    Existing fields with the same ``name`` are skipped (so a re-detect
    doesn't blow away operator-supplied source paths). Detected fields
    are created with ``source_path=None``; the operator must map them in
    the editor before finalize.
    """
    template = repo.get_template(db, template_id)
    if template is None:
        raise LookupError(f"Template {template_id} not found")
    _ensure_draft(template)

    existing_names = {
        f.name for f in repo.list_template_fields(db, template_id)
    }
    created: list[InsuranceFormTemplateField] = []
    for idx, df in enumerate(detected):
        if df.name in existing_names:
            continue
        spec = FieldSpec(
            name=df.name,
            label=df.label,
            page=df.page,
            kind=df.kind if df.kind in _VALID_KINDS else "text",
            bbox=df.bbox,
            sort_order=idx,
        )
        created.append(add_field(db, template_id=template_id, spec=spec))
    return created


def finalize_template(
    db: Session, *, template_id: _uuid.UUID
) -> InsuranceFormTemplate:
    """Lock a draft template after sanity-checking the field map.

    Pre-conditions:
    * Template must be in ``draft`` status.
    * Must have at least one field.
    * Every field with ``required=True`` must have a non-empty
      ``source_path`` (so the fill service can attempt to populate it).
    """
    template = repo.get_template(db, template_id)
    if template is None:
        raise LookupError(f"Template {template_id} not found")
    if template.status != "draft":
        raise TemplateLockedError(
            f"Template {template_id} is already {template.status}"
        )
    fields = repo.list_template_fields(db, template_id)
    if not fields:
        raise TemplateNotReadyError(
            f"Template {template_id} has no fields; add at least one before finalize"
        )
    missing = [
        cast(str, f.name) for f in fields if cast(bool, f.required) and not cast(str, f.source_path or "").strip()
    ]
    if missing:
        raise TemplateNotReadyError(
            "Required fields missing source_path: " + ", ".join(missing)
        )
    return repo.mark_finalized(db, template)


def clone_for_edit(
    db: Session, *, template_id: _uuid.UUID
) -> InsuranceFormTemplate:
    """Create a new draft version of a finalized template, copying field map."""
    src = repo.get_template(db, template_id)
    if src is None:
        raise LookupError(f"Template {template_id} not found")

    new = repo.create_template(
        db,
        org_id=cast(_uuid.UUID, src.org_id),
        name=cast(str, src.name),
        carrier=cast(str | None, src.carrier),
        s3_bucket=cast(str | None, src.s3_bucket),
        s3_key=cast(str | None, src.s3_key),
        sha256=cast(str | None, src.sha256),
        page_count=cast(int | None, src.page_count),
        created_by_user_id=cast(_uuid.UUID | None, src.created_by_user_id),
    )
    for f in repo.list_template_fields(db, template_id):
        db.add(
            InsuranceFormTemplateField(
                template_id=new.id,
                name=f.name,
                label=f.label,
                page=f.page,
                kind=f.kind,
                bbox_json=f.bbox_json,
                source_path=f.source_path,
                transform=f.transform,
                required=f.required,
                default_value=f.default_value,
                sort_order=f.sort_order,
            )
        )
    db.commit()
    db.refresh(new)
    return new
