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
└── integrity/
    └── checksums.sha256             # SHA-256 checksums of every file above
```

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
