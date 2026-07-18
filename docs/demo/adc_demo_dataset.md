# ADC deterministic demo dataset

## Reference date and idempotency

The expanded local demo workspace uses a fixed reference date of **2026-07-15 15:00 UTC**. Relative dates in tasks, incident aging, timeline rows, and export expiry are calculated from that fixed instant so screenshots and tests remain stable.

Seed records use deterministic UUIDv5 identifiers scoped by organization plus fixture key. Re-running the seed updates stable users, drivers, vehicles, incidents, and deletes/recreates incident child records for the demo incidents so notes, tasks, evidence, timeline events, and exports do not duplicate.

Reset path:

```bash
make local-reset
make local-bootstrap
make local-verify-demo
```

## Demo identity

- Organization: `ADC Demo Org`
- Administrator: `demo-admin@adc.local`
- Password: `DemoAdmin!2345`

Additional fictional users are seeded for administrative and case assignment views:

| Email | Demo role |
| --- | --- |
| claims.director@adc.local | Claims Director |
| safety.manager@adc.local | Safety Manager |
| fleet.manager@adc.local | Fleet Manager |
| claims.analyst@adc.local | Claims Analyst |
| legal.ops@adc.local | Legal Operations Specialist |

## Featured incidents

| Reference | Scenario | Expected posture |
| --- | --- | --- |
| `ADC-DEMO-2026-001` | Serious commercial tractor-trailer collision near Braselton, GA | Escalated, high severity, not ready, overdue work, missing police report, ready/queued document activity |
| `ADC-DEMO-2026-002` | Cargo theft at a Memphis cross-dock | Awaiting evidence, not ready, cargo and bill-of-lading evidence gaps, active export workflow |
| `ADC-DEMO-2026-003` | Minor property damage at a Jacksonville receiver | Ready for export, high readiness, mostly complete evidence, ready defense document |

## Dataset totals and distributions

The seed creates at least:

- 6 organization users including the preserved demo admin.
- 26 expanded incidents plus the legacy scenario incident used by the scenario launcher.
- 14 fictional drivers.
- 14 vehicle registry units.
- 112 evidence artifact records across `captured`, `pending`, and `unavailable` states.
- 46 case tasks across `open`, `blocked`, and `completed`, including overdue work assigned to the demo admin.
- 42 professional case notes.
- 128 incident timeline/activity events.
- 23 exports/documents including ready, requested, queued, processing, failed, and expired records, with one retry relationship.

Incident status distribution intentionally includes `new`, `in_review`, `awaiting_evidence`, `awaiting_follow_up`, `ready_for_export`, `exported`, `escalated`, and `closed`.

Evidence types include photographs, driver statements, police reports, dashcam video, vehicle inspections, ELD logs, insurance documents, witness information, bills of lading, cargo inventory, repair estimates, and supporting correspondence.

Task titles include police report requests, driver statements, scene photo review, dashcam review, vehicle inspection confirmation, insurance carrier contact, witness statement collection, bill-of-lading requests, cargo inventory review, and defense packet generation.

Export statuses include ready, requested, queued, processing, failed, and expired. Failed exports use safe business reasons such as `document rendering failure` and `missing required evidence`.

## Known data-model limitations

- Incident display labels such as case reference, title, narrative location, and incident type are represented in deterministic event payloads and documentation because the current `incidents` table does not expose dedicated columns for those labels.
- Evidence requests and evidence files share the current `artifacts` model, whose supported states are `pending`, `captured`, and `unavailable`.
- Vehicles are represented through `org_vehicle_registry` and driver assignments; make/model/year are not currently first-class fields in the active vehicle registry model.
- Ready export rows include metadata, checksum, size, bucket, and key. Live download behavior still depends on the configured local artifact/storage service.
