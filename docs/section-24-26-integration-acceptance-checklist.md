# Sections 24–26 Integration & Diagnostics Acceptance Checklist

This checklist adds explicit QA scenarios for Sections 24–26 and ties each scenario to automated coverage (API/integration tests) plus go-live runbook validation.

> Delivery tracking for Sections 26–28 is maintained in `docs/operations/section-26-28-readiness-backlog.md` (Sprints 1–5 with owners, estimates, dependencies, DoD, and KPI targets).

## Section 24 acceptance criteria (integration reliability)

- [ ] **AC-24.1 Invalid credentials are treated as intervention-required**
  - Expected behavior: integration connection moves to `error`, operation result requires re-auth, retries do not loop indefinitely.
- [ ] **AC-24.2 Missing/stale mappings are surfaced as mapping-fix-required**
  - Expected behavior: telematics capture fails with `vehicle_mapping_missing`-style reasoning and admin action guidance.
- [ ] **AC-24.3 Provider timeout and provider-side rate limiting are retry-classified**
  - Expected behavior: transient dependency failures are classified retryable with capability backoff policy.
- [ ] **AC-24.4 Partial telematics success is non-blocking for export workflows**
  - Expected behavior: capture/export can complete with warnings when optional evidence is unavailable.

## Section 25 acceptance criteria (async callbacks & webhook safety)

- [ ] **AC-25.1 Async dashcam readiness/state transition is persisted for diagnostics**
  - Expected behavior: operation transitions and external reference IDs are persisted for asynchronous provider flows.
- [ ] **AC-25.2 OTP undelivered callback is reconciled into message operation state**
  - Expected behavior: Twilio status callback updates message operation to `undelivered`/`failed` and records webhook event.
- [ ] **AC-25.3 Invalid webhook signatures are denied and auditable**
  - Expected behavior: webhook returns 403, records a failed webhook event, and surfaces signature validation reason.

## Section 26 acceptance criteria (diagnostics isolation & export warning fidelity)

- [ ] **AC-26.1 Org isolation is enforced in diagnostics and evidence views**
  - Expected behavior: integration diagnostics only show rows from caller org scope.
- [ ] **AC-26.2 Export packages preserve warning/missing evidence diagnostics**
  - Expected behavior: export build remains resilient, writes warnings/missing items for unavailable evidence.

## Scenario-to-acceptance mapping

| Requested QA scenario | Section acceptance criteria | Automated coverage | Go-live validation command/script |
| --- | --- | --- | --- |
| invalid credentials | AC-24.1 | `backend/tests/test_celery_tasks.py::TestCaptureTelematicsBundle::test_credentials_invalid_marks_connection_for_reauth` | `bash scripts/run_section24_26_qa.sh invalid_credentials` |
| mapping missing/stale | AC-24.2 | `backend/tests/test_job_retry_policy.py::test_classify_normalized_error_non_retryable_for_mapping` | `bash scripts/run_section24_26_qa.sh mapping_missing_or_stale` |
| provider timeout and rate limiting | AC-24.3 | `backend/tests/test_job_retry_policy.py::test_classify_retry_exception_transient_dependency`, `backend/tests/test_production_hardening_suite.py::test_rate_limit_enforcement_returns_429_when_threshold_hit` | `bash scripts/run_section24_26_qa.sh provider_timeout_rate_limit` |
| partial telematics success | AC-24.4 | `backend/tests/test_export_section23_acceptance.py::test_partial_artifact_soft_fail_behavior` | `bash scripts/run_section24_26_qa.sh partial_telematics_success` |
| async dashcam ready callback | AC-25.1 | `backend/tests/test_celery_tasks.py::TestCaptureDashcam::test_dashcam_operation_state_machine_and_external_reference_id` | `bash scripts/run_section24_26_qa.sh dashcam_async_ready` |
| OTP undelivered callback | AC-25.2 | `backend/tests/test_twilio_routes.py::test_twilio_status_callback_reconciles_message_operation` | `bash scripts/run_section24_26_qa.sh otp_undelivered_callback` |
| webhook signature invalid paths | AC-25.3 | `backend/tests/test_twilio_routes.py::test_twilio_voice_rejects_missing_signature`, `backend/tests/test_twilio_routes.py::test_twilio_voice_persists_invalid_signature_event` | `bash scripts/run_section24_26_qa.sh invalid_webhook_signature` |
| org isolation in diagnostics | AC-26.1 | `backend/tests/test_api_endpoints.py::TestIntegrationDiagnosticsRoutes::test_integration_operations_and_evidence_summary` | `bash scripts/run_section24_26_qa.sh diagnostics_org_isolation` |
| export warnings from missing evidence | AC-26.2 | `backend/tests/test_celery_tasks.py::TestBuildExport::test_export_soft_fail_persists_warnings`, `backend/tests/test_production_hardening_suite.py::test_storage_outage_simulation_keeps_export_zip_generation_resilient` | `bash scripts/run_section24_26_qa.sh export_missing_evidence_warnings` |


## Weather provider integration epic QA entries

These entries supplement Section 24 integration reliability for the weather-provider epic. Detailed setup, troubleshooting, operational signals, and manual evidence requirements live in `docs/weather-provider-integration-runbook.md`.

| Epic acceptance criterion | QA checklist entry | Automated coverage | Operational signal to verify |
| --- | --- | --- | --- |
| WX-AC-1 NWS capture is non-blocking and normalized. | Validate successful and partial NWS captures produce requested/captured lifecycle events without blocking incident initiation. | `backend/tests/services/test_nws_client.py`, `backend/tests/services/test_nws_parser.py`, `backend/tests/services/test_weather_snapshot_service.py` | `weather_snapshot_capture`, `integration.provider.requests`, `integration.provider.success`, `integration.provider.failure` |
| WX-AC-2 Location fallback order is deterministic. | Validate device location wins before current ELD GPS, last-known ELD state, then unavailable reason codes. | `backend/tests/test_incident_location_resolver.py` | Event payload fields `location.source` and `location.fallback_reason` |
| WX-AC-3 Weather map captures Mapbox base image and TWC overlay when both providers are healthy. | Validate captured map event includes `overlay_applied=true`, `twc_radar_timestamp`, and persisted `weather_map_snapshot` artifact. | `backend/tests/services/test_weather_map_snapshot_service.py` | `weather_map_snapshot_capture` with `provider=mapbox+twc`, `status=ok`, `artifact_id` |
| WX-AC-4 TWC overlay failure degrades without blocking the incident workflow. | Validate base-map-only artifact capture with `capture_status=degraded` and admin-visible overlay reason. | `backend/tests/services/test_weather_map_snapshot_service.py` | `overlay_applied=false`, `overlay_unavailable_reason`, elevated degradation ratio |
| WX-AC-5 Missing location or provider/storage hard failure produces actionable diagnostics. | Validate failed events include reason/fallback fields and user-facing copy keeps the accident workflow usable. | `backend/tests/services/test_weather_snapshot_service.py`, `backend/tests/services/test_weather_map_snapshot_service.py`, `backend/tests/test_incident_workflow_service.py` | `capture_status=failed`, `reason`, `location.fallback_reason`, `integration.provider.failure` |
| WX-AC-6 Accident PDF weather update scope is limited to `crash_brief`. | Validate the initial accident PDF update changes only the `crash_brief` rendering path unless another PDF acceptance criterion is approved. | `backend/tests/test_crash_packet_builder.py`, `backend/tests/test_pdf_render_templates.py`, `backend/tests/test_export_pdf_service.py` | Release evidence links rendered `crash_brief` PDF and notes no unrelated PDF template changes |
| WX-AC-7 On-call can diagnose without code spelunking. | Validate staging emits searchable logs, metrics, event payload fields, and alert hints for ok/degraded/failed weather captures. | Runbook review plus backend CI checks | Dashboards/log queries include `incident_id`, `provider`, `status`, `latency`, `reason`, `artifact_id` |
