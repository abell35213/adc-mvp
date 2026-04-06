# Driver Protocol Test Matrix (MVP + Production-Ready)

This matrix defines QA coverage for critical driver protocol resilience and data-integrity paths. It maps each scenario to:

1. **MVP acceptance criteria** (what must work now).
2. **Production-ready criteria** (hardening requirements before broad rollout).
3. **Required evidence** from app telemetry + backend timeline/audit artifacts.

## Acceptance criteria catalog

### MVP acceptance criteria (MVP-*)

- **MVP-01 OTP recovery:** Driver can recover from invalid/expired/locked OTP by requesting a new challenge and successfully signing in.
- **MVP-02 Vehicle QR resolution:** Valid QR resolves vehicle and invalid QR gives actionable error without blocking alternate vehicle path.
- **MVP-03 Incident initiation resiliency:** Startup handles duplicate/ambiguous failures and allows retry/resume without creating duplicate incidents.
- **MVP-04 Draft durability:** Scene/narrative edits persist locally and are recoverable on resume.
- **MVP-05 Upload retry durability:** Media upload queue survives app restarts and retries with bounded backoff.
- **MVP-06 Submit gate correctness:** Submit blocks when minimum required sections are incomplete or uploads are failed.
- **MVP-07 Access isolation:** Driver cannot read/write incidents outside their ownership/org boundary.

### Production-ready criteria (PR-*)

- **PR-01 Auth observability/SLO:** OTP failures segmented by cause (invalid/expired/locked/rate-limited/provider) with alerting thresholds.
- **PR-02 QR quality controls:** QR failures segmented by reason (malformed/deactivated/not found/permission denied) and trend monitored.
- **PR-03 Startup idempotency & timeout SLO:** Initiation API is idempotent and timeout recovery success rate meets SLO.
- **PR-04 Crash/restart continuity:** Resume UX and draft reconciliation tested across cold restart/app upgrade cases.
- **PR-05 Durable upload orchestration:** Retry reason codes, attempt histograms, and terminal failure workflow are auditable.
- **PR-06 Compliance submit controls:** Submit decision is explainable from persisted state and incident status snapshots.
- **PR-07 Tenant/incident data controls:** Cross-org and cross-incident isolation validated in API and timeline write paths with regression tests.

## Test matrix

| ID | Scenario | Core test cases | MVP criteria | Production-ready criteria | Required telemetry + timeline evidence |
|---|---|---|---|---|---|
| TM-01 | OTP auth and expiry recovery | 1) Request OTP + verify happy path. 2) Invalid code returns auth failure. 3) Locked challenge returns lock response. 4) Expired challenge behavior validates new challenge request + successful verify. | MVP-01 | PR-01 | **Telemetry:** OTP request/verify attempts with result and reason code. **Timeline/audit:** challenge status transitions (`pending` → `verified`/`locked`/`expired`) and timestamped retry path. |
| TM-02 | Vehicle QR success/failure | 1) QR token resolves to expected vehicle. 2) Bad token format rejected in app. 3) API invalid token rejected with user-facing retry. 4) Fallback to assigned vehicle remains available. | MVP-02 | PR-02 | **Telemetry:** `qr_scan_started`, `qr_scan_success`, `qr_scan_failed` (+ `invalid_token`). **Timeline:** incident payload shows selected vehicle strategy and resolved vehicle ID at initiation. |
| TM-03 | Initiation on poor/no network and timeout recovery | 1) Simulate network failure during `/incidents/initiate`; verify retry prompt. 2) Simulate timeout (>12s) and verify ambiguous recovery path checks active incident. 3) If active incident exists, continue without duplicate start. | MVP-03 | PR-03 | **Telemetry:** `incident_initiated` with correlation IDs; startup failure counters by reason (`network`, `timeout`, `api`). **Timeline:** single `incident_protocol_initiated` event for recovered flow and no duplicate evidence-capture task fan-out. |
| TM-04 | Duplicate active incident behavior | 1) Repeated initiation with same idempotency key returns existing incident. 2) Existing active incident for driver is reused. 3) App shows resume guidance when duplicate/conflict indicated. | MVP-03 | PR-03 | **Telemetry:** duplicate-hit metric and idempotency-key reuse rate. **Timeline:** one initiation event per incident + proof no duplicate capture/notify jobs enqueued. |
| TM-05 | Scene/narrative save and resume correctness | 1) Save scene step-by-step and kill app; reopen and verify recovered draft. 2) Save narrative as draft, restart, ensure text restored. 3) Verify cross-incident local draft mismatch does not auto-apply to new active incident. | MVP-04 | PR-04 | **Telemetry:** `scene_saved`, `narrative_saved`, `protocol_resumed` (with route). **Timeline:** driver scene/narrative events persisted when server reachable; local-storage fallback noted in client logs when offline. |
| TM-06 | Media upload retry after app restart | 1) Queue media upload, force transient upload failure, confirm retry scheduled. 2) Restart app/process and verify queue hydration + retry continuation. 3) Verify terminal failure emits failure event after max attempts. | MVP-05 | PR-05 | **Telemetry:** `driver_upload_attempted`, `driver_upload_retry_scheduled`, `driver_upload_succeeded`/`driver_upload_failed`, protocol analytics upload success/failure. **Timeline:** `driver_media_uploaded` or `driver_media_upload_failed` with artifact type + queue item metadata. |
| TM-07 | Partial completion + submit rules | 1) Attempt submit with missing minimum routes; verify blocked with explicit error. 2) Attempt submit when uploads failed; verify blocked. 3) Submit allowed when minimum routes complete and capture state not failed. | MVP-06 | PR-06 | **Telemetry:** submit-attempt outcome metric (`blocked_minimum`, `blocked_upload_failed`, `submitted`). **Timeline:** `driver_report_submitted` emitted only for successful submit path. |
| TM-08 | Cross-org/cross-incident access restrictions | 1) Driver A cannot patch/report/timeline/status for Driver B incident (same org). 2) Driver from different org cannot patch/read another org incident. 3) Verify API returns non-disclosing not-found response. | MVP-07 | PR-07 | **Telemetry:** authorization rejection counters by endpoint and scope mismatch. **Timeline/audit:** no write events created for rejected requests; access-denied logs include driver/org/incident correlation IDs. |

## Evidence capture checklist per test execution

For each matrix case above, capture and attach:

1. **Test run context:** environment, app build SHA, backend SHA, device/os.
2. **Correlation IDs:** `workflow_correlation_id` and `incident_correlation_id` used in app analytics payloads.
3. **API traces:** request/response status + body excerpts for relevant endpoints.
4. **Timeline proof:** persisted incident events with `event_type`, `actor_type`, and `occurred_at_utc`.
5. **Pass/fail decision:** explicit mapping to MVP-* and PR-* criteria IDs.

## Existing implementation hooks that support this matrix

- OTP challenge and error-state coverage exists in backend auth endpoint tests.
- Driver incident initiation tests already validate idempotency/duplicate-active reuse behavior.
- Driver app emits protocol analytics for QR, initiation, resume, scene/narrative save, and upload outcomes.
- Review/submit gate already enforces minimum route completion and blocks submit on failed uploads.
- Driver report/timeline/status endpoints have negative tests for cross-driver and cross-org restrictions.
