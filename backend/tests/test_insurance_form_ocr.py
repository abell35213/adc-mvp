"""Tests for insurance form field detection (plan test #7)."""

from __future__ import annotations

import pytest

from app.services.insurance_form_ocr import (
    AcroFormFieldDetectionProvider,
    DetectedField,
    DetectionResult,
    NoopFieldDetectionProvider,
    _textract_blocks_to_fields,
    get_provider,
    register_provider,
)


class TestNoopProvider:
    def test_returns_empty_result(self):
        provider = NoopFieldDetectionProvider()
        result = provider.detect(content=b"anything", content_type="application/pdf")
        assert isinstance(result, DetectionResult)
        assert result.fields == []
        assert result.provider == "noop"

    def test_via_registry_default_falls_back(self):
        # Unknown provider name → noop fallback (logs a warning).
        provider = get_provider("totally-not-a-provider")
        assert provider.name == "noop"


class TestAcroFormProvider:
    """The Acro provider tolerates non-PDF / unfillable content gracefully.

    Using a real fillable PDF in the test suite would require shipping a
    binary fixture. Instead we drive the provider through pypdf's own
    code-path by passing bytes that pypdf cannot parse, asserting that
    the provider returns an empty result with the expected ``warning`` —
    which covers the operator-facing "no fields detected" UX.
    """

    def test_unparseable_content_produces_warning(self):
        provider = AcroFormFieldDetectionProvider()
        result = provider.detect(content=b"not a pdf", content_type="application/pdf")
        assert result.provider == "acroform"
        assert result.fields == []
        # Either pypdf isn't installed, or it parsed and rejected the bytes;
        # both surface as a non-empty warning.
        assert result.warning is not None

    def test_parsed_pdf_with_no_acroform_fields_warns(self, monkeypatch):
        """Simulate pypdf returning a PDF with zero AcroForm fields."""
        provider = AcroFormFieldDetectionProvider()

        class _FakeReader:
            pages = [object(), object()]  # 2 pages

            def get_fields(self):
                return None

        # Patch the lazy import path: pypdf.PdfReader → our fake.
        import sys
        from types import SimpleNamespace

        fake_pypdf = SimpleNamespace(PdfReader=lambda *_a, **_k: _FakeReader())
        monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)

        result = provider.detect(content=b"%PDF-fake", content_type="application/pdf")
        assert result.fields == []
        assert result.page_count == 2
        assert result.warning == "no_acroform_fields"

    def test_parsed_pdf_with_acroform_fields_extracted(self, monkeypatch):
        provider = AcroFormFieldDetectionProvider()

        class _FakeReader:
            pages = [object()]

            def get_fields(self):
                return {
                    "DriverName": {"/FT": "/Tx", "/TU": "Driver Name"},
                    "Signature": {"/FT": "/Sig", "/TU": "Signature"},
                    "DOTNumber": {"/FT": "/Tx"},  # no /TU → falls back to name
                    "ConsentBox": {"/FT": "/Btn", "/TU": "Consent"},
                }

        import sys
        from types import SimpleNamespace

        monkeypatch.setitem(
            sys.modules,
            "pypdf",
            SimpleNamespace(PdfReader=lambda *_a, **_k: _FakeReader()),
        )

        result = provider.detect(content=b"%PDF-fake", content_type="application/pdf")
        assert result.warning is None
        names = {f.name for f in result.fields}
        assert names == {"DriverName", "Signature", "DOTNumber", "ConsentBox"}
        kinds = {f.name: f.kind for f in result.fields}
        assert kinds["DriverName"] == "text"
        assert kinds["Signature"] == "signature"
        assert kinds["ConsentBox"] == "checkbox"
        # The /TU label is preferred over the field name.
        labels = {f.name: f.label for f in result.fields}
        assert labels["DriverName"] == "Driver Name"
        # Falls back to the name when /TU is absent.
        assert labels["DOTNumber"] == "DOTNumber"

    def test_get_fields_exception_surfaces_warning(self, monkeypatch):
        provider = AcroFormFieldDetectionProvider()

        class _FakeReader:
            pages = []

            def get_fields(self):
                raise RuntimeError("pypdf blew up")

        import sys
        from types import SimpleNamespace

        monkeypatch.setitem(
            sys.modules,
            "pypdf",
            SimpleNamespace(PdfReader=lambda *_a, **_k: _FakeReader()),
        )
        result = provider.detect(content=b"%PDF-x", content_type="application/pdf")
        assert result.fields == []
        assert result.warning is not None
        assert "get_fields_failed" in result.warning


class TestTextractBlockReducer:
    def test_extracts_key_labels_and_skips_non_keys(self):
        blocks = [
            {
                "Id": "k1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Page": 1,
                "Relationships": [{"Type": "CHILD", "Ids": ["w1", "w2"]}],
            },
            {"Id": "w1", "BlockType": "WORD", "Text": "Driver"},
            {"Id": "w2", "BlockType": "WORD", "Text": "Name"},
            # A VALUE block — should be ignored.
            {
                "Id": "v1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["VALUE"],
                "Relationships": [{"Type": "CHILD", "Ids": ["w3"]}],
            },
            {"Id": "w3", "BlockType": "WORD", "Text": "Pat"},
            # A LINE — should be ignored.
            {"Id": "l1", "BlockType": "LINE", "Text": "Header"},
        ]
        fields = _textract_blocks_to_fields(blocks)
        assert len(fields) == 1
        assert fields[0].name == "Driver Name"
        assert fields[0].label == "Driver Name"
        assert fields[0].page == 1

    def test_empty_label_is_skipped(self):
        blocks = [
            {
                "Id": "k1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}],
            },
            {"Id": "w1", "BlockType": "WORD", "Text": ""},
        ]
        assert _textract_blocks_to_fields(blocks) == []


class TestRegistry:
    def test_register_then_get(self):
        class _Custom:
            name = "custom-field-detector"

            def detect(self, *, content, content_type):
                return DetectionResult(
                    provider=self.name,
                    fields=[DetectedField(name="x")],
                )

        register_provider(_Custom())
        provider = get_provider("custom-field-detector")
        result = provider.detect(content=b"", content_type="application/pdf")
        assert result.fields[0].name == "x"

    def test_default_provider_is_acroform(self):
        assert get_provider().name == "acroform"


class TestDetectedFieldDataclass:
    def test_defaults(self):
        f = DetectedField(name="x")
        assert f.kind == "text"
        assert f.label is None
        assert f.page is None
        assert f.bbox is None

    def test_is_frozen(self):
        f = DetectedField(name="x")
        with pytest.raises(Exception):
            f.name = "y"  # type: ignore[misc]
