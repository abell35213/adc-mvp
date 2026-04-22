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

