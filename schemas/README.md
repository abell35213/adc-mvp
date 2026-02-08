# ADC Court Artifact Schemas (v1)

This repository starter contains the "court artifact contract" for Accident Defense Command (ADC).
Engineering MUST validate generated JSON against these schemas before writing artifacts to the vault.

## Versioning rules
- `schema_version` is required in every JSON artifact. Current: "1.0".
- Backward compatible changes only within major version:
  - ✅ Add optional fields
  - ✅ Add new enum values only if existing values remain valid
  - ❌ Remove fields
  - ❌ Change field types
  - ❌ Reorder CSV columns (CSV column order is locked)

## Timestamp rules
- All *_utc fields must be RFC3339 "date-time" in UTC (e.g., 2026-02-08T08:21:00Z).
- ADC server time is canonical for:
  - `generated_at_utc`
  - `capture_window.start_utc/end_utc`
  - `captured_at_utc`
  - custody times

## Narrative rules (court safety)
- No free-form narrative fields are allowed, except:
  - `unavailable_reason_detail` (short, factual)
  - `detail` in custody entries (system-generated only)

## Required top-level envelope
All artifact JSON files share a common envelope:
- schema_version
- generated_at_utc
- incident_id
- carrier_id
- vehicle (adc_vehicle_id, samsara_vehicle_id)
- capture_window (start_utc, end_utc, request_reason)
- source_system ("samsara" for the provided schemas)
- artifacts (artifact_id, related_artifact_ids)
- data (artifact-specific)

## Validation
- Validate JSON artifacts against the schema file with the same name.
- Fail loudly: if validation fails, emit capture-failed events + unavailable artifacts (no silent gaps).
