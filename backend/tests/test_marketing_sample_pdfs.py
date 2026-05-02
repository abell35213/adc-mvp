"""Tests for the marketing-site sample PDF generator.

These tests verify that:
 - the legal_defense_packet template is registered and renders;
 - the generator script's three sample contexts all produce non-empty PDFs;
 - sample PDFs include the SAMPLE watermark and the Carrier ABC fixture.

Per repo convention, ``backend/tests/conftest.py`` autouse-monkeypatches
``sys.modules['weasyprint'].HTML`` to return deterministic fingerprinted
PDF bytes, so these tests do not need WeasyPrint's native deps.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services.pdf_render import TEMPLATE_REGISTRY, render_html

# Load ``backend/scripts/generate_marketing_sample_pdfs.py`` by file path.
# We deliberately avoid ``from scripts.X import …`` because the repo root also
# contains a top-level ``scripts/`` package (used by, e.g.,
# ``tests/test_runtime_contract_snapshot.py``); making ``backend/scripts/`` a
# regular package would shadow it on sys.path.
_GENERATOR_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "generate_marketing_sample_pdfs.py"
)
_spec = importlib.util.spec_from_file_location(
    "generate_marketing_sample_pdfs", _GENERATOR_PATH
)
assert _spec is not None and _spec.loader is not None
_generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_generator)

SAMPLES = _generator.SAMPLES
build_executive_brief_context = _generator.build_executive_brief_context
build_insurance_form_context = _generator.build_insurance_form_context
build_legal_defense_packet_context = _generator.build_legal_defense_packet_context
generate_all = _generator.generate_all


def test_legal_defense_packet_template_registered() -> None:
    assert "legal_defense_packet" in TEMPLATE_REGISTRY
    assert TEMPLATE_REGISTRY["legal_defense_packet"] == "legal_defense_packet.html"


@pytest.mark.parametrize(
    "template_name,builder",
    [
        ("crash_brief", build_executive_brief_context),
        ("insurance_form", build_insurance_form_context),
        ("legal_defense_packet", build_legal_defense_packet_context),
    ],
)
def test_sample_contexts_render_without_raising(template_name: str, builder) -> None:
    html = render_html(template_name, builder())
    assert html, "expected non-empty HTML"
    # Watermark is opt-in via the is_sample flag; sample contexts must enable it.
    assert "sample-document" in html
    # Carrier identity must thread through every doc (executive brief
    # references it implicitly via incident metadata; the legal packet
    # references it explicitly; the insurance form references it as the
    # Named Insured).
    if template_name in {"insurance_form", "legal_defense_packet"}:
        assert "Carrier ABC" in html


def test_generate_all_writes_three_pdfs(tmp_path: Path) -> None:
    written = generate_all(output_dir=tmp_path)
    assert len(written) == len(SAMPLES) == 3
    for path in written:
        assert path.exists()
        data = path.read_bytes()
        assert data.startswith(b"%PDF"), f"{path.name} did not start with %PDF"
        assert len(data) > 0
    # Filenames must be exactly what the marketing UI references.
    names = sorted(p.name for p in written)
    assert names == [
        "adc-sample-executive-brief.pdf",
        "adc-sample-insurance-form.pdf",
        "adc-sample-legal-defense-packet.pdf",
    ]


def test_insurance_form_context_lists_missing_required_fields() -> None:
    ctx = build_insurance_form_context()
    # User asked for a "realistic partial" fill — we must surface the
    # missing-required warning (claim number from carrier, etc.).
    assert ctx["missing_required_fields"], "expected at least one missing required field"
    html = render_html("insurance_form", ctx)
    assert "Missing required fields" in html
