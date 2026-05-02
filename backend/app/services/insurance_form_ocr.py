"""Field detection for uploaded insurance form templates (Phase 3).

A *field detection provider* takes the bytes of a blank form (PDF or
image) and returns a list of :class:`DetectedField` rows that the operator
can then map onto canonical source paths in the template editor.

Three providers ship out of the box:

* :class:`NoopFieldDetectionProvider` — returns no fields. Used as a safe
  default when no upstream OCR is configured; the operator will define
  every field by hand.
* :class:`AcroFormFieldDetectionProvider` — extracts named AcroForm fields
  from a fillable PDF. ``pypdf`` is imported lazily so the module loads
  without it (and the provider degrades gracefully if it isn't installed).
* :class:`TextractFieldDetectionProvider` — sketch wired to AWS Textract
  ``AnalyzeDocument`` (FORMS feature). ``boto3`` is also lazy-imported.
  Tests do not exercise the live path; they assert configuration plumbing.

A small registry function :func:`get_provider` picks the right provider
by name so callers don't import provider classes directly. This mirrors
the ``email_provider`` / ``twilio_notify`` capability/registry pattern
used elsewhere in the codebase.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DetectedField:
    """One field discovered on a blank insurance form.

    Operators see this in the template editor and assign a ``source_path``
    + optional ``transform`` to it before finalize.
    """

    name: str
    label: str | None = None
    page: int | None = None
    kind: str = "text"  # one of: text, date, checkbox, signature
    bbox: dict | None = None  # {x, y, w, h} in normalized [0, 1] page coords


@dataclass
class DetectionResult:
    """Outcome of running a provider on a single uploaded form."""

    provider: str
    fields: list[DetectedField] = field(default_factory=list)
    page_count: int | None = None
    warning: str | None = None


class FieldDetectionProvider(Protocol):
    """Common interface for all template-upload field detectors."""

    name: str

    def detect(
        self, *, content: bytes, content_type: str
    ) -> DetectionResult:  # pragma: no cover - structural
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Providers
# ─────────────────────────────────────────────────────────────────────────────


class NoopFieldDetectionProvider:
    """Returns no detected fields. The operator defines every field manually."""

    name = "noop"

    def detect(self, *, content: bytes, content_type: str) -> DetectionResult:
        del content, content_type
        return DetectionResult(provider=self.name, fields=[], page_count=None)


# AcroForm widget-type → our :class:`InsuranceFormTemplateField.kind` enum.
_ACRO_KIND_MAP = {
    "/Tx": "text",
    "/Btn": "checkbox",
    "/Sig": "signature",
    "/Ch": "text",
}


class AcroFormFieldDetectionProvider:
    """Pulls named AcroForm fields out of a fillable PDF using pypdf.

    Returns an empty result with a ``warning`` if the PDF is unparseable,
    has no AcroForm dictionary, or if pypdf is not installed.
    """

    name = "acroform"

    def detect(self, *, content: bytes, content_type: str) -> DetectionResult:
        del content_type  # we always treat content as a PDF
        try:
            import pypdf  # noqa: PLC0415 - lazy/optional
        except ImportError:
            return DetectionResult(
                provider=self.name,
                fields=[],
                warning="pypdf_not_installed",
            )

        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001 - any pypdf parse error
            logger.info(
                "AcroForm detection: PDF parse failed: %s", exc, exc_info=True
            )
            return DetectionResult(
                provider=self.name, fields=[], warning=f"pdf_parse_failed: {exc}"
            )

        page_count = len(reader.pages)

        # ``get_form_text_fields`` only returns text fields. Use the lower-level
        # ``get_fields`` so we capture checkboxes + signatures too.
        try:
            raw_fields = reader.get_fields()
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "AcroForm detection: get_fields failed: %s", exc, exc_info=True
            )
            return DetectionResult(
                provider=self.name,
                fields=[],
                page_count=page_count,
                warning=f"get_fields_failed: {exc}",
            )

        if not raw_fields:
            return DetectionResult(
                provider=self.name,
                fields=[],
                page_count=page_count,
                warning="no_acroform_fields",
            )

        detected: list[DetectedField] = []
        for name, info in raw_fields.items():
            ft = None
            label = None
            if isinstance(info, dict):
                ft = info.get("/FT")
                # ``/TU`` (TextField user-name) is the human-friendly label.
                label = info.get("/TU") or info.get("/T") or name
            kind = _ACRO_KIND_MAP.get(str(ft) if ft is not None else "", "text")
            detected.append(
                DetectedField(
                    name=str(name),
                    label=str(label) if label is not None else None,
                    page=None,
                    kind=kind,
                    bbox=None,
                )
            )
        return DetectionResult(
            provider=self.name,
            fields=detected,
            page_count=page_count,
        )


class TextractFieldDetectionProvider:
    """AWS Textract ``AnalyzeDocument`` (FORMS) wrapper.

    ``boto3`` is lazy-imported. Only invoked in deployments where the
    operator has explicitly chosen Textract; tests use the noop or
    acroform providers.
    """

    name = "textract"

    def __init__(self, *, region: str | None = None) -> None:
        self.region = region

    def detect(self, *, content: bytes, content_type: str) -> DetectionResult:
        del content_type
        try:
            import boto3  # noqa: PLC0415
        except ImportError:
            return DetectionResult(
                provider=self.name,
                fields=[],
                warning="boto3_not_installed",
            )
        client = boto3.client("textract", region_name=self.region)
        try:
            response = client.analyze_document(
                Document={"Bytes": content}, FeatureTypes=["FORMS"]
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Textract analyze_document failed: %s", exc)
            return DetectionResult(
                provider=self.name,
                fields=[],
                warning=f"textract_failed: {exc}",
            )
        return DetectionResult(
            provider=self.name,
            fields=_textract_blocks_to_fields(response.get("Blocks", [])),
        )


def _textract_blocks_to_fields(blocks: list[dict]) -> list[DetectedField]:
    """Reduce a Textract block stream into our :class:`DetectedField` list.

    Pulls ``KEY`` blocks (the visible label) and resolves their paired
    ``VALUE`` block via the standard ``CHILD`` / ``VALUE`` relationships.
    The MVP only needs the label name — bbox/page can be wired later.
    """
    by_id = {b["Id"]: b for b in blocks if "Id" in b}
    out: list[DetectedField] = []
    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in (block.get("EntityTypes") or []):
            continue
        # Walk CHILD relationship to find the WORD blocks that make up the label.
        label_words: list[str] = []
        for rel in block.get("Relationships") or []:
            if rel.get("Type") == "CHILD":
                for cid in rel.get("Ids") or []:
                    child = by_id.get(cid)
                    if child and child.get("BlockType") == "WORD":
                        label_words.append(child.get("Text", ""))
        label = " ".join(w for w in label_words if w).strip() or None
        if not label:
            continue
        out.append(
            DetectedField(
                name=label,  # operator can rename later
                label=label,
                page=block.get("Page"),
                kind="text",
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────


_REGISTRY: dict[str, FieldDetectionProvider] = {
    "noop": NoopFieldDetectionProvider(),
    "acroform": AcroFormFieldDetectionProvider(),
}


def register_provider(provider: FieldDetectionProvider) -> None:
    """Add (or replace) a provider in the registry — used by tests."""
    _REGISTRY[provider.name] = provider


def get_provider(name: str | None = None) -> FieldDetectionProvider:
    """Return the named provider, defaulting to ``acroform``.

    Unknown names fall back to ``noop`` and log a warning so a
    misconfigured ``INSURANCE_FORM_OCR_PROVIDER`` env var degrades safely.
    """
    if name is None:
        return _REGISTRY["acroform"]
    provider = _REGISTRY.get(name)
    if provider is None:
        logger.warning(
            "Unknown field-detection provider %r; falling back to noop", name
        )
        return _REGISTRY["noop"]
    return provider
