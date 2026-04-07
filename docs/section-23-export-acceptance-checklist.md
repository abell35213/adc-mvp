# Section 23 Export Workflow Acceptance Checklist (MVP + Production)

This checklist maps directly to Section 23 export workflow expectations, with explicit traceability to test coverage.

## MVP criteria (Section 23 MVP)

- [ ] **MVP-23.1 Authorization and org isolation**
  - Evidence: `test_authorization_and_org_isolation` validates same-org success and cross-org denial for create/detail endpoints.
- [ ] **MVP-23.2 Lifecycle transitions** (`requested → queued → processing → ready/failed`)
  - Evidence: `test_lifecycle_requested_to_queued_to_processing_and_ready` and `test_hard_fail_path_sets_failed_status`.
- [ ] **MVP-23.3 Manifest + integrity output presence**
  - Evidence: `test_manifest_and_integrity_outputs` validates manifest JSON, package integrity JSON, and checksums.
- [ ] **MVP-23.4 Partial artifact retrieval soft-fail**
  - Evidence: `test_partial_artifact_soft_fail_behavior` validates ready completion with warnings/missing items.
- [ ] **MVP-23.5 Retry semantics for failed exports**
  - Evidence: `test_retry_semantics` validates retry chain linkage and queued status.

## Production criteria (Section 23 production-ready)

- [ ] **PR-23.1 End-to-end minimal incident export**
  - Evidence: `test_e2e_minimal_incident_generates_ready_export`.
- [ ] **PR-23.2 End-to-end rich incident export**
  - Evidence: `test_e2e_rich_incident_includes_multiple_artifact_folders`.
- [ ] **PR-23.3 Missing optional artifacts remain non-blocking**
  - Evidence: `test_e2e_missing_optional_artifacts_still_ready`.
- [ ] **PR-23.4 PDF renderer failure hard-fails export**
  - Evidence: `test_e2e_pdf_failure_behavior_sets_failed`.
- [ ] **PR-23.5 Single artifact retrieval failure soft-fails package build**
  - Evidence: `test_e2e_single_artifact_retrieval_failure_soft_fails`.
- [ ] **PR-23.6 Frontend workflow states validated**
  - Evidence: `frontend/tests/exportFlowModel.test.mjs` covers modal flow, polling, ready/download, and detail visibility logic.

## Sign-off fields

- Date:
- Reviewer:
- Environment:
- Result summary:
