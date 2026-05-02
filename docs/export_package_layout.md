# Export Package Layout

> Court-facing specification for the ADC evidence export ZIP package.

## ZIP Folder Structure

```
ADC_Export_{incident_id}_{YYYYMMDD}/
├── metadata/
│   ├── evidence_inventory.json      # Full inventory of collected evidence
│   └── chain_of_custody.json        # Tamper-evident custody log
├── gps/
│   ├── gps_trace.json               # Raw GPS trace artifact
│   └── gps_trace.csv                # GPS points as CSV
├── eld/
│   ├── eld_duty_status.json         # ELD duty-status artifact
│   └── eld_duty_status.csv          # Duty-status changes as CSV
├── safety/
│   ├── safety_events.json           # Safety/harsh events artifact
│   └── safety_events.csv            # Events as CSV
├── vehicle/
│   ├── vehicle_state.json           # Vehicle state snapshots artifact
│   └── vehicle_state.csv            # Snapshots as CSV
├── media/
│   └── *.mp4 / *.jpg                # Dashcam clips & stills (if available)
├── loading_dock/
│   └── *.jpg / *.png                # Loading-dock photos + signature scans
│                                    # (linked many-to-one via
│                                    # Artifact.loading_dock_report_id)
├── weigh_tickets/
│   └── *.pdf / *.jpg                # Scanned weigh tickets
│                                    # (artifact_type = 'weigh_ticket')
├── dispatch/
│   └── *.pdf / *.jpg                # Dispatch sheet packets
│                                    # (artifact_type = 'dispatch_sheet')
└── integrity/
    └── checksums.sha256             # SHA-256 checksums of every file above
```

> **Phase 3 evidence in the cover-summary PDF.** Dispatch instructions,
> weigh-station reports, and loading-dock reports are persisted in
> `dispatch_instructions`, `weigh_station_reports`, and
> `loading_dock_reports` respectively. They flow into the `Initial Crash
> Brief` PDF via `app.services.crash_packet_query.fetch_crash_packet_row`
> (direct `incident_id` FK match, falling back to the 24h trip-context
> window keyed on driver / vehicle / trailer). They are part of the
> legal-hold export bundle: the rows are serialized into the brief PDF,
> and any linked dock photo (`Artifact.loading_dock_report_id IS NOT
> NULL` with `incident_id` set) is included in the `loading_dock/`
> subfolder by the standard artifact-bundling pass.

> **Out-of-scope (follow-on imaging-integration project).** External
> weigh-feed integrations (FMCSA SAFER, PrePass) and TMS imaging
> products (e.g. McLeod Imaging) that auto-attach digitized scale
> tickets and dispatch sheets are intentionally not implemented in this
> milestone. The schema is laid out so they slot in without further
> churn: an `Artifact` row with `artifact_type='weigh_ticket'` or
> `'dispatch_sheet'` and a `loading_dock_report_id` FK (or, for weigh
> tickets, a future direct FK) lands in the corresponding subfolder
> automatically.

## Filenames per Artifact Type

| Artifact Type       | JSON Filename              | CSV Filename              |
|---------------------|----------------------------|---------------------------|
| GPS Trace           | `gps_trace.json`           | `gps_trace.csv`           |
| ELD Duty Status     | `eld_duty_status.json`     | `eld_duty_status.csv`     |
| Safety Events       | `safety_events.json`       | `safety_events.csv`       |
| Vehicle State       | `vehicle_state.json`       | `vehicle_state.csv`       |
| Evidence Inventory  | `evidence_inventory.json`  | —                         |
| Chain of Custody    | `chain_of_custody.json`    | —                         |

## Required CSV Headers

CSV column order is **locked** within a schema major version. Do not reorder.

### gps_trace.csv

```
timestamp_utc,latitude,longitude,speed_mph,heading_deg,odometer_mi,source
```

### eld_duty_status.csv

```
timestamp_utc,status,driver_id,driver_name,location_description,odometer_mi,engine_hours,source
```

### safety_events.csv

```
timestamp_utc,event_type,severity,latitude,longitude,speed_mph,driver_id,driver_name,source
```

### vehicle_state.csv

```
timestamp_utc,ignition,speed_mph,odometer_mi,fuel_pct,latitude,longitude,source
```

## Integrity Appendix Format

The file `integrity/checksums.sha256` contains one line per file using the standard
`sha256sum` output format:

```
<64-char-hex-digest>  <relative-path-from-zip-root>
```

Example:

```
a1b2c3d4...  metadata/evidence_inventory.json
e5f6a7b8...  gps/gps_trace.json
9c0d1e2f...  gps/gps_trace.csv
```

### Verification

Recipients can verify the package with:

```bash
cd ADC_Export_{incident_id}_{YYYYMMDD}/
sha256sum -c integrity/checksums.sha256
```

All lines should report `OK`. Any mismatch indicates the file was altered after
the export was generated.

## PDF Rendering Pipeline

PDF documents inside the export ZIP (cover summary, telematics dataset
reports, vehicle QR printables) are produced by a single rendering pipeline:

```
context dict --> Jinja2 template (backend/app/templates/pdf/) --> HTML
HTML        --> WeasyPrint (HTML(string=...).write_pdf())     --> PDF bytes
```

The single entry point is `app.services.pdf_render.render_pdf(template_name,
context)`. Template names are resolved through the `TEMPLATE_REGISTRY` dict
in that module; unknown names raise `ValueError`. Renders that fail or
return empty bytes raise `RuntimeError` (hard-fail) so the export package
cannot be persisted with a missing/corrupt document. For development
environments only, setting `PDF_RENDER_FAIL_OPEN=true` makes the renderer
return a placeholder PDF on engine errors instead of raising.

Adding a new document type:

1. Add `<name>.html` under `backend/app/templates/pdf/` (extend `base.html`
   to inherit shared `@page` rules and typography).
2. Register it in `TEMPLATE_REGISTRY` in `app/services/pdf_render.py`.
3. Add a context-builder helper alongside the existing
   `*_pdf_context.py` modules to keep callers thin.
4. Add a unit test in `backend/tests/test_pdf_render_templates.py` that
   asserts the key context fields appear in the rendered HTML; this runs
   without WeasyPrint's native dependencies.

See `backend/docs/pdf-rendering.md` for the developer-facing rundown.

