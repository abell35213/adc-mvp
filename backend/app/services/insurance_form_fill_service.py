"""Insurance form fill orchestration service (Phase 3).

Given an incident and a *finalized* template, this service:

1. Builds the canonical :class:`CrashPacketRow` (single SQL pass — same
   helper Phase 1 uses for the crash brief).
2. Resolves each template field's ``source_path`` + ``transform`` against
   the row to produce a flat ``{field_name: value}`` payload.
3. Captures any ``required=True`` fields whose value resolved to ``None``
   on the resulting :class:`InsuranceFormFilling` row and short-circuits
   to ``status='failed'`` if any were missing.
4. Renders the filled PDF via the existing ``pdf_render`` infrastructure
   and (optionally) hands the bytes to a pluggable :class:`S3Writer`.
5. Writes an ``Artifact`` row of type ``insurance_form_filled`` and links
   it from the :class:`InsuranceFormFilling`.

The service is **idempotent** on ``(incident_id, template_id, payload_hash)``:
re-running with unchanged canonical data returns the existing filling and
does not create a duplicate Artifact.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.db.models import (
    Artifact,
    InsuranceFormFilling,
    InsuranceFormTemplate,
    InsuranceFormTemplateField,
)
from app.db.repo import insurance_form_fillings as fillings_repo
from app.db.repo import insurance_form_templates as templates_repo
from app.services.crash_packet_query import fetch_crash_packet_row
from app.services.insurance_form_path_resolver import (
    resolve_with_transform,
    row_to_root,
)
from app.services.pdf_render import render_pdf

logger = logging.getLogger(__name__)


INSURANCE_FORM_TEMPLATE = "insurance_form"
ARTIFACT_TYPE = "insurance_form_filled"


# ─────────────────────────────────────────────────────────────────────────────
# Pluggable S3 writer
# ─────────────────────────────────────────────────────────────────────────────


class S3Writer(Protocol):
    """Writes ``content`` to a bucket and returns ``(bucket, key)``.

    Real implementation wraps ``boto3.client("s3").put_object``. Unit
    tests pass a noop writer that returns ``(None, None)`` so the
    ``Artifact`` row is created without S3 metadata.
    """

    def __call__(
        self, *, content: bytes, content_type: str, suggested_key: str
    ) -> tuple[str | None, str | None]:  # pragma: no cover - structural
        ...


def noop_s3_writer(
    *, content: bytes, content_type: str, suggested_key: str
) -> tuple[None, None]:
    """Default writer for environments without S3 (incl. tests)."""
    del content, content_type, suggested_key
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolvedField:
    """A single template field after resolution against the canonical row."""

    name: str
    label: str | None
    source_path: str | None
    value: Any
    required: bool


@dataclass
class FillResult:
    """Return type from :func:`fill_form_for_incident`."""

    filling: InsuranceFormFilling
    created: bool  # False when an existing idempotent filling was returned
    pdf_bytes: bytes | None  # None when the existing filling is returned


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _payload_hash(
    template_id: _uuid.UUID,
    template_version: int,
    resolved: list[ResolvedField],
) -> str:
    """Stable SHA-256 over template identity + resolved values.

    Including the template identity in the hash means a re-fill *with the
    same data* against a new template version still re-runs (the version
    number is part of the input), preventing a stale Artifact from being
    silently surfaced as the new template's output.
    """
    payload = {
        "template_id": str(template_id),
        "template_version": template_version,
        "fields": [
            {
                "name": r.name,
                "source_path": r.source_path,
                "value": r.value,
                "required": r.required,
            }
            for r in sorted(resolved, key=lambda r: r.name)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _resolve_fields(
    fields: list[InsuranceFormTemplateField], root: dict[str, Any]
) -> list[ResolvedField]:
    out: list[ResolvedField] = []
    for f in fields:
        value: Any
        if f.source_path:
            value = resolve_with_transform(root, f.source_path, f.transform)
            if value is None and f.default_value is not None:
                value = f.default_value
        else:
            value = f.default_value
        out.append(
            ResolvedField(
                name=f.name,
                label=f.label,
                source_path=f.source_path,
                value=value,
                required=bool(f.required),
            )
        )
    return out


def _missing_required(resolved: list[ResolvedField]) -> list[str]:
    return [r.name for r in resolved if r.required and r.value is None]


def _serialize_value(value: Any) -> Any:
    """Coerce datetimes etc. into JSON-safe types for storage / hash."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def fill_form_for_incident(
    db: Session,
    *,
    incident_id: _uuid.UUID,
    template_id: _uuid.UUID,
    s3_writer: S3Writer | None = None,
) -> FillResult:
    """Fill ``template_id`` for ``incident_id`` and return the result.

    Pre-conditions:

    * Template must exist and be in ``finalized`` status.
    * Incident must exist (``fetch_crash_packet_row`` raises if it does
      not — the ``LookupError`` propagates).

    On any required-field-missing error the filling is still recorded
    (status=``failed``) so operators can see it in the case workspace.
    Render errors are also recorded and re-raised.
    """
    template = templates_repo.get_template(db, template_id)
    if template is None:
        raise LookupError(f"InsuranceFormTemplate {template_id} not found")
    if template.status != "finalized":
        raise ValueError(
            f"Template {template_id} is {template.status}; finalize before fill"
        )

    fields = templates_repo.list_template_fields(db, template_id)

    row = fetch_crash_packet_row(db, incident_id=incident_id)
    root = row_to_root(row)
    resolved = _resolve_fields(fields, root)

    # Serialize for the JSON payload (datetimes → iso strings, etc.).
    serialized = [
        ResolvedField(
            name=r.name,
            label=r.label,
            source_path=r.source_path,
            value=_serialize_value(r.value),
            required=r.required,
        )
        for r in resolved
    ]

    payload_hash = _payload_hash(template_id, template.version, serialized)

    existing = fillings_repo.find_existing(
        db,
        incident_id=incident_id,
        template_id=template_id,
        payload_hash=payload_hash,
    )
    if existing is not None:
        return FillResult(filling=existing, created=False, pdf_bytes=None)

    missing = _missing_required(serialized)
    payload_json = {
        "fields": [
            {
                "name": r.name,
                "label": r.label,
                "source_path": r.source_path,
                "value": r.value,
                "required": r.required,
            }
            for r in serialized
        ]
    }

    if missing:
        # Record the failed attempt for operator visibility, but do not
        # render or upload anything.
        filling = InsuranceFormFilling(
            incident_id=incident_id,
            template_id=template_id,
            template_version=template.version,
            status="failed",
            payload_json=payload_json,
            payload_hash=payload_hash,
            missing_required_fields=missing,
            error_message=(
                "Required field(s) missing source data: " + ", ".join(missing)
            ),
        )
        db.add(filling)
        db.commit()
        db.refresh(filling)
        return FillResult(filling=filling, created=True, pdf_bytes=None)

    # Render the filled PDF.
    now = datetime.now(timezone.utc)
    context = {
        "subject": f"Insurance form: {template.name}",
        "template": _serialize_template(template),
        "incident": row.incident_json,
        "filled_at_utc": now.isoformat(),
        "fields": [
            {
                "name": r.name,
                "label": r.label,
                "source_path": r.source_path,
                "value": r.value,
            }
            for r in serialized
        ],
        "missing_required_fields": missing,
    }

    try:
        pdf_bytes = render_pdf(INSURANCE_FORM_TEMPLATE, context)
    except Exception as exc:
        filling = InsuranceFormFilling(
            incident_id=incident_id,
            template_id=template_id,
            template_version=template.version,
            status="failed",
            payload_json=payload_json,
            payload_hash=payload_hash,
            missing_required_fields=missing,
            error_message=f"render_failed: {exc}",
        )
        db.add(filling)
        db.commit()
        db.refresh(filling)
        raise

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    writer = s3_writer or noop_s3_writer
    suggested_key = (
        f"insurance_forms/{incident_id}/{template_id}/{payload_hash[:16]}.pdf"
    )
    bucket, key = writer(
        content=pdf_bytes,
        content_type="application/pdf",
        suggested_key=suggested_key,
    )

    artifact = Artifact(
        org_id=template.org_id,
        incident_id=incident_id,
        artifact_type=ARTIFACT_TYPE,
        status="captured",
        s3_bucket=bucket,
        s3_key=key,
        sha256=sha256,
        byte_size=len(pdf_bytes),
        uploaded_at_utc=now,
    )
    db.add(artifact)
    db.flush()  # populate artifact_id

    filling = InsuranceFormFilling(
        incident_id=incident_id,
        template_id=template_id,
        template_version=template.version,
        status="filled",
        payload_json=payload_json,
        payload_hash=payload_hash,
        output_artifact_id=artifact.artifact_id,
        missing_required_fields=[],
        filled_at_utc=now,
    )
    db.add(filling)
    db.commit()
    db.refresh(filling)

    return FillResult(filling=filling, created=True, pdf_bytes=pdf_bytes)


def _serialize_template(template: InsuranceFormTemplate) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "name": template.name,
        "carrier": template.carrier,
        "version": template.version,
        "status": template.status,
    }
