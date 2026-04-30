# PDF Rendering

ADC export documents (cover summary, telematics dataset reports, vehicle QR
printables) are produced by a single Jinja2 + WeasyPrint pipeline. Callers
do not import WeasyPrint directly; they go through one entry point:

```python
from app.services.pdf_render import render_pdf

pdf_bytes = render_pdf(
    "vehicle_qr_printable",
    {"vehicle_id": "UNIT-1", "qr_token": "tok", "qr_image_data_uri": None},
)
```

## Layout

```
backend/app/templates/pdf/
├── base.html                       # Shared <html> skeleton + @page rules
├── partials/
│   ├── _header.html                # Title block (title, package, generated_at)
│   └── _footer.html                # Verification reminder line
├── static/
│   └── base.css                    # Print styles (typography, tables, page numbers)
├── cover_summary.html              # 00_Cover_Summary.pdf in export ZIPs
├── telematics_report.html          # gps/eld/safety/vehicle dataset PDFs
└── vehicle_qr_printable.html       # Vehicle QR printable handout
```

The template lookup table lives in `app/services/pdf_render.py` as
`TEMPLATE_REGISTRY`. Templates are resolved by logical name (e.g.
`"cover_summary"`), not by file path, so callers stay decoupled from the
on-disk layout.

## Failure policy

`render_pdf` raises `ValueError` for unknown template names and
`RuntimeError` for empty / failed renders. Setting
`PDF_RENDER_FAIL_OPEN=true` switches the renderer to return a small
placeholder PDF on engine errors — intended for non-production
environments only.

## Adding a new document type

1. Drop `<name>.html` into `backend/app/templates/pdf/`. Inherit from
   `base.html` (`{% extends "base.html" %}`) so you get the shared CSS and
   `@page` rules for free.
2. Register the template in `TEMPLATE_REGISTRY` in
   `app/services/pdf_render.py`.
3. If the context shaping is non-trivial, add a context-builder helper
   next to `app/services/telematics_pdf_context.py`. Keep call sites
   (Celery tasks, FastAPI routes) thin.
4. Add a unit test to `backend/tests/test_pdf_render_templates.py` that
   exercises `render_html(...)` and asserts the important context fields
   appear in the HTML. This test path **does not** require WeasyPrint's
   native libraries to be installed.

## Native dependencies

WeasyPrint requires Pango / Cairo / GDK-PixBuf / HarfBuzz at runtime:

| Platform | Install |
| --- | --- |
| Docker (production) | Already provisioned in `backend/Dockerfile`. |
| Debian / Ubuntu | `apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info fonts-dejavu` |
| macOS | `brew install pango cairo gdk-pixbuf libffi` |

Unit tests do **not** need these libraries: `backend/tests/conftest.py`
auto-uses a fixture that monkey-patches `sys.modules["weasyprint"]` with a
stub that returns deterministic fake PDF bytes.

## Opt-in real-WeasyPrint integration test

`tests/test_pdf_render_templates.py` defines a smoke test marked
`@pytest.mark.weasyprint_native` that actually invokes WeasyPrint. It is
skipped unless `ADC_RUN_WEASYPRINT_NATIVE=1` is set, so it only runs in
environments (such as the Docker build) where the native libs are present:

```bash
ADC_RUN_WEASYPRINT_NATIVE=1 pytest tests/test_pdf_render_templates.py -m weasyprint_native
```
