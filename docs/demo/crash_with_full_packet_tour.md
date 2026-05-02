# Guided Tour — `crash_with_full_packet` Demo Scenario

This scenario demonstrates the **end-to-end ADC crash workflow** built across
Phases 1, 2, and 3 of the demo-workflow stream. Launching it from the demo
console (or seeding it directly) produces a single incident that is
simultaneously:

1. Eligible for the **Phase 1** crash-notification packet (status
   `accident_occurred`, with a sent `CrashPacketDelivery` row),
2. Backed by **Phase 2** trailer + maintenance history pulled into the
   canonical `CrashPacketRow`, and
3. Filled into a **Phase 3** insurance form template, producing a
   downloadable `insurance_form_filled` artifact.

The deterministic verifier `scripts/verify_demo.py` (also exposed as
`make verify-demo`) asserts every record below is present and well-formed.

---

## How to launch

```bash
# From the demo workspace UI:
#   Settings → Demo workspace → Scenarios → "Crash with full insurance packet"

# Or programmatically:
python -c "
from app.commercial.demo import seed_demo_tenant
# … pass an Org and ORG_ADMIN actor
"

# CI smoke test (offline, no Postgres / Celery / SES needed):
make verify-demo
```

---

## What gets seeded

Each item below maps to one row (or set of rows) in the demo DB.

### Phase 1 — Crash notification packet

| Record | Notes |
|---|---|
| `Incident` (`status='accident_occurred'`, `severity='serious'`) | The packet hook fires on this transition in production. |
| `OrgNotificationRecipient` (`email='claims-demo@adc.local'`) | Active recipient of the email channel; the per-org control file. |
| `CrashPacketDelivery` (`status='sent'`) | Idempotency key `demo-crashpacket-<incident_id>`. The seeder writes this row directly so the demo viewer sees a successful delivery without standing up Celery + SES. |

### Phase 2 — Trailer + maintenance + driver assignment

| Record | Notes |
|---|---|
| `Driver` (`display_name='Pat Demo-Driver'`) | Phone-uniqueness preserved by salting the org id. |
| `DriverVehicleAssignment` | Manual source, links the driver to `veh-demo-crashpacket-001`. |
| `Trailer` (`adc_trailer_id='trl-demo-crashpacket-001'`, VIN `TRDEMO00000000001`) | Joined to the incident via `incident.adc_trailer_id`. |
| `MaintenanceRecord` × 3 | Two tractor records (14 days, 120 days ago) and one trailer record (45 days ago). All within the canonical 1-year window. |

### Phase 3 — Insurance form template + fill

| Record | Notes |
|---|---|
| `InsuranceFormTemplate` (`name='ACORD-DEMO'`, `status='finalized'`) | Carrier `DemoMutual`. |
| `InsuranceFormTemplateField` × 4 | `DriverName` (required, `upper` transform), `VehicleUnit`, `TrailerVIN`, `LastMaintVendor`. |
| `InsuranceFormFilling` (`status='filled'`) | Resolved against the canonical `CrashPacketRow` for the seeded incident; `missing_required_fields == []`. |
| `Artifact` (`artifact_type='insurance_form_filled'`) | The rendered PDF, with `sha256` + `byte_size` populated. |

---

## What the verifier checks

`scripts/verify_demo.py` exits non-zero if any of the following fail:

- The seeder return payload contains every Phase 1+2+3 id (8 keys).
- `Incident.status == 'accident_occurred'` and `adc_trailer_id` is set.
- Exactly one `CrashPacketDelivery` exists, status `sent`.
- Exactly one active `OrgNotificationRecipient` exists.
- One `Trailer` and three `MaintenanceRecord` rows exist, mixing
  `tractor` and `trailer` asset kinds.
- `Driver` row `'Pat Demo-Driver'` was created.
- `InsuranceFormTemplate` is `finalized`.
- `InsuranceFormFilling` is `filled`, with empty `missing_required_fields`
  and a non-null `output_artifact_id`.
- The corresponding `Artifact` is of type `insurance_form_filled` and has
  bytes written.
- The fill resolved values **from the canonical row** (proving Phase 3's
  resolver actually walked the joined `CrashPacketRow`):
  - `DriverName == 'PAT DEMO-DRIVER'` (Driver join + `upper` transform),
  - `TrailerVIN == 'TRDEMO00000000001'` (Phase 2 trailer table),
  - `LastMaintVendor == 'ShopAlpha'` (newest maintenance row),
  - `VehicleUnit == 'veh-demo-crashpacket-001'` (incident column).

---

## Resetting the scenario

`launch_scenario` calls `reset_demo_tenant` first, which has been extended
to clean up the new tables:

- `Trailer` rows whose `adc_trailer_id` starts with `trl-demo-`,
- `MaintenanceRecord` rows whose `asset_id` starts with `veh-demo-` or
  `trl-demo-`,
- `Driver` + `DriverVehicleAssignment` rows for `'Pat Demo-Driver'`,
- `OrgNotificationRecipient` rows with email `claims-demo@adc.local`,
- `InsuranceFormFilling` (incident-scoped, `CASCADE`-safe) and
  `InsuranceFormTemplate` rows whose name starts with `ACORD-DEMO`,
- `CrashPacketDelivery` rows for the deleted incidents.

Re-running the scenario after a reset should produce a fresh incident id
and one new copy of every record above; the test suite asserts this.
