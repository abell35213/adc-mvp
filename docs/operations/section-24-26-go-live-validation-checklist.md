# Sections 24–26 Go-Live Validation Checklist

Use this checklist during release readiness sign-off for integration reliability, callback safety, and diagnostics/export integrity.

## Pre-flight

- [ ] Confirm staging environment has representative orgs, incidents, mappings, and provider sandbox credentials.
- [ ] Confirm worker queue and webhook ingress are enabled.
- [ ] Confirm on-call engineer has access to diagnostics endpoints and logs.

## Section 24 — Integration reliability

- [ ] **Invalid credentials (AC-24.1)**
  - Validate `reauth_required` behavior and integration connection error state.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh invalid_credentials`.
- [ ] **Mapping missing/stale (AC-24.2)**
  - Validate mapping failure reason and admin-action guidance.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh mapping_missing_or_stale`.
- [ ] **Provider timeout and rate limiting (AC-24.3)**
  - Validate retry classification/backoff and API 429 protections.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh provider_timeout_rate_limit`.
- [ ] **Partial telematics success (AC-24.4)**
  - Validate export is non-blocking with warning records.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh partial_telematics_success`.

## Section 25 — Async callbacks and webhook safety

- [ ] **Async dashcam ready/state transitions (AC-25.1)**
  - Validate operation transitions + external reference observability.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh dashcam_async_ready`.
- [ ] **OTP undelivered callback (AC-25.2)**
  - Validate message status reconciliation from callback payload.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh otp_undelivered_callback`.
- [ ] **Invalid webhook signature paths (AC-25.3)**
  - Validate HTTP 403 and failed webhook-event persistence.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh invalid_webhook_signature`.

## Section 26 — Diagnostics isolation and export warning fidelity

- [ ] **Org isolation in diagnostics (AC-26.1)**
  - Validate cross-org operations are not visible to caller org.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh diagnostics_org_isolation`.
- [ ] **Export warnings from missing evidence (AC-26.2)**
  - Validate missing evidence produces warnings instead of hard-fail package generation.
  - Evidence: attach output from `bash scripts/run_section24_26_qa.sh export_missing_evidence_warnings`.

## Sign-off

- Release version/tag:
- Date (UTC):
- Environment:
- QA lead:
- SRE/on-call approver:
- Result summary (include blockers, waivers, and follow-ups):
