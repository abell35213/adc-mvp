#!/usr/bin/env bash
set -euo pipefail

SCENARIO="${1:-all}"

cat <<'USAGE' >&2
Section 24–26 QA runbook helper.

Usage:
  bash scripts/run_section24_26_qa.sh <scenario>

Scenarios:
  invalid_credentials
  mapping_missing_or_stale
  provider_timeout_rate_limit
  partial_telematics_success
  dashcam_async_ready
  otp_undelivered_callback
  invalid_webhook_signature
  diagnostics_org_isolation
  export_missing_evidence_warnings
  all
USAGE

print_step() {
  local scenario_name="$1"
  shift
  if [[ "$SCENARIO" == "all" || "$SCENARIO" == "$scenario_name" ]]; then
    echo
    echo "=== ${scenario_name} ==="
    "$@"
  fi
}

invalid_credentials() {
  cat <<'EOF_STEP'
1) Deactivate or rotate integration credentials in non-prod.
2) Trigger telematics capture for a known incident.
3) Verify operation outcome includes admin action `reauth_required`.
4) Verify integration connection transitions to status `error`.
Reference test: backend/tests/test_celery_tasks.py::TestCaptureTelematicsBundle::test_credentials_invalid_marks_connection_for_reauth
EOF_STEP
}

mapping_missing_or_stale() {
  cat <<'EOF_STEP'
1) Remove vehicle mapping for a test incident's vehicle/provider pair.
2) Trigger telematics capture.
3) Confirm response/reason includes mapping issue (`vehicle_mapping_missing`).
4) Confirm diagnostics indicate admin action `mapping_fix_required`.
Reference test: backend/tests/test_job_retry_policy.py::test_classify_normalized_error_non_retryable_for_mapping
EOF_STEP
}

provider_timeout_rate_limit() {
  cat <<'EOF_STEP'
1) Inject provider timeout (e.g., proxy delay/fault) and trigger capture.
2) Confirm retry classification is transient and backoff policy is applied.
3) Send API calls beyond configured threshold and confirm HTTP 429 + Retry-After.
Reference tests:
- backend/tests/test_job_retry_policy.py::test_classify_retry_exception_transient_dependency
- backend/tests/test_production_hardening_suite.py::test_rate_limit_enforcement_returns_429_when_threshold_hit
EOF_STEP
}

partial_telematics_success() {
  cat <<'EOF_STEP'
1) Simulate one optional telematics artifact unavailable while others are present.
2) Build export package.
3) Confirm export remains `ready` with warning entries.
Reference test: backend/tests/test_export_section23_acceptance.py::test_partial_artifact_soft_fail_behavior
EOF_STEP
}

dashcam_async_ready() {
  cat <<'EOF_STEP'
1) Trigger dashcam capture with provider external reference recorded.
2) Verify integration operation status transitions are persisted.
3) Validate external reference is visible in diagnostics output.
Reference test: backend/tests/test_celery_tasks.py::TestCaptureDashcam::test_dashcam_operation_state_machine_and_external_reference_id
EOF_STEP
}

otp_undelivered_callback() {
  cat <<'EOF_STEP'
1) Submit Twilio status callback with MessageStatus=undelivered for a known MessageSid.
2) Confirm MessageOperation status updates to `undelivered` and webhook event is persisted.
Reference test: backend/tests/test_twilio_routes.py::test_twilio_status_callback_reconciles_message_operation
EOF_STEP
}

invalid_webhook_signature() {
  cat <<'EOF_STEP'
1) Submit webhook callback with missing/invalid X-Twilio-Signature.
2) Confirm endpoint returns HTTP 403.
3) Confirm ProviderWebhookEvent is persisted with invalid signature outcome.
Reference tests:
- backend/tests/test_twilio_routes.py::test_twilio_voice_rejects_missing_signature
- backend/tests/test_twilio_routes.py::test_twilio_voice_persists_invalid_signature_event
EOF_STEP
}

diagnostics_org_isolation() {
  cat <<'EOF_STEP'
1) Create integration operations in Org A and Org B.
2) Query diagnostics as Org A admin.
3) Confirm only Org A operations and evidence summaries are returned.
Reference test: backend/tests/test_api_endpoints.py::TestIntegrationDiagnosticsRoutes::test_integration_operations_and_evidence_summary
EOF_STEP
}

export_missing_evidence_warnings() {
  cat <<'EOF_STEP'
1) Force artifact download failure during export build.
2) Confirm export zip still generates and includes warning/missing-item records.
Reference tests:
- backend/tests/test_celery_tasks.py::TestBuildExport::test_export_soft_fail_persists_warnings
- backend/tests/test_production_hardening_suite.py::test_storage_outage_simulation_keeps_export_zip_generation_resilient
EOF_STEP
}

print_step "invalid_credentials" invalid_credentials
print_step "mapping_missing_or_stale" mapping_missing_or_stale
print_step "provider_timeout_rate_limit" provider_timeout_rate_limit
print_step "partial_telematics_success" partial_telematics_success
print_step "dashcam_async_ready" dashcam_async_ready
print_step "otp_undelivered_callback" otp_undelivered_callback
print_step "invalid_webhook_signature" invalid_webhook_signature
print_step "diagnostics_org_isolation" diagnostics_org_isolation
print_step "export_missing_evidence_warnings" export_missing_evidence_warnings
