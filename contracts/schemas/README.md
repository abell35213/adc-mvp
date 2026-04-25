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

### `$id` URI convention
- Every schema file declares an `$id` of the form
  `https://adc.example/schemas/<artifact_name>.schema.json`. The host is a
  stable identifier, not a fetchable URL — schemas are resolved from the
  in-repo `contracts/schemas/` directory at validation time.
- Filenames and `$id` basenames are locked once published. To rename an
  artifact, introduce a new schema with a new `$id` and run both in parallel
  through the deprecation window below.
- Bumping the major version (i.e. emitting a breaking change) requires a new
  `$id` of the form
  `https://adc.example/schemas/v2/<artifact_name>.schema.json` and a new
  `schema_version` const (e.g. `"2.0"`). Validators must continue to accept
  `v1` artifacts for at least one full deprecation cycle.

### Deprecation policy
1. **Announce** — open an RFC and tag the schema's top-level `description`
   with `Deprecated: <date>, removal target <date+180d>`.
2. **Dual-write** — generators emit both the old and new artifact for the
   duration of the deprecation window so downstream consumers can switch on
   their own schedule. Validation suites must accept both.
3. **Switch reads** — flip frontend / driver-app / vault consumers to the
   new schema; capture telemetry for any `schema_version` reads that still
   match the deprecated value.
4. **Remove** — once telemetry has been silent for at least 30 consecutive
   days (and not before the announced removal target), delete the deprecated
   schema and add a `forbidden_schema_versions` entry to the validator so the
   removal is enforced server-side.

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


## Runtime API contract snapshot
- `runtime_api_contracts.json` is generated from `backend/app/api/schemas.py` and captures the backend response/request contract consumed by the frontend.
- Regenerate after backend schema updates:
  - `python scripts/generate_runtime_api_contract.py`
- CI and backend tests both enforce drift detection:
  - `python scripts/generate_runtime_api_contract.py --check`
