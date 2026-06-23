# Priority-2 production hardening gate evidence

This document is the authoritative evidence roll-up for the Priority-2 hardening
gates (sections 10–21 of `docs/production-hardening/program-plan.md`). Each gate
below maps to exactly one entry in `docs/production-hardening/checklist.yaml`.

Priority-2 gates are **not** enforced by `scripts/check_release_hardening_gates.py`
(which blocks production tags only on incomplete Priority-1 gates). They are
tracked here so the production-readiness review has a single, auditable source of
truth for the supporting controls, runbooks, and tests.

## Status legend

- **complete** — control is implemented and the cited evidence (runbook, tests,
  and/or infrastructure manifests) exists in-repo.
- **deferred** — control has a deliberate in-repo abstraction/seam, but full
  external integration is intentionally out of scope for this release. The
  disposition and re-activation path are recorded in section 2 below.

## 1) Priority-2 gate evidence (sections 10–21)

| Section | Gate | Status | Acceptance criteria | Evidence artifacts |
| --- | --- | --- | --- | --- |
| 10 | secrets_management | complete | Runtime secrets are vaulted in AWS Secrets Manager, fetched at runtime, and rotated via a documented redeploy-safe procedure; no secrets in source. | `infra/production/externalsecret.yaml`, `backend/app/core/config.py`, `scripts/rotate_runtime_secrets.sh`, `docs/api-keys-rotation-runbook.md`, `docs/db-credentials-rotation-runbook.md`, `docs/jwt-key-rotation-runbook.md`, `backend/tests/test_config.py` |
| 11 | data_encryption | complete | Data is encrypted in transit (TLS) and at rest (managed Postgres/object-store encryption); evidence artifacts use validated, integrity-checked object keys. | `infra/production/backend-deployment.yaml`, `infra/production/object-storage-policies.yaml`, `backend/app/services/vault_s3.py`, `backend/app/services/s3_key_builder.py`, `backend/tests/test_vault_s3.py`, `backend/tests/test_s3_key_builder.py` |
| 12 | dependency_vulnerability | complete | Dependency/image scanning runs in CI and blocks release on high-severity issues; accepted residuals are documented with justification. | `.github/workflows/ci.yml` (`dependency-vulnerability-scan`), `docs/production-hardening/release-gate-evidence.md` §4, `docs/release-readiness-checklist.md` |
| 13 | api_contract_governance | complete | Runtime API contract is versioned and drift-checked in CI; schema versioning and deprecation policy are documented. | `contracts/schemas/README.md`, `scripts/generate_runtime_api_contract.py`, `backend/tests/test_runtime_contract_snapshot.py`, `backend/tests/test_frontend_contracts.py` |
| 14 | iac_conformance | complete | Production infrastructure is provisioned via reviewed, reproducible manifests (deployments, service account, network policy, PDB, backups, storage policy). | `infra/production/backend-deployment.yaml`, `infra/production/serviceaccount.yaml`, `infra/production/networkpolicy.yaml`, `infra/production/poddisruptionbudget.yaml`, `infra/production/postgres-backup-cronjob.yaml`, `infra/production/object-storage-policies.yaml` |
| 15 | access_lifecycle | complete | Least-privilege is enforced (no cluster RBAC bound to workload SA; org-scoped authorization); credential/key rotation runbooks define offboarding/rotation. | `infra/production/serviceaccount.yaml`, `backend/app/security/permissions.py`, `backend/app/core/deps.py`, `docs/jwt-key-rotation-runbook.md`, `backend/tests/test_authorization_regressions.py` |
| 16 | retention_legal_hold | complete | Object versioning + lifecycle retention and backup retention schedules are defined; restore validation confirms recoverability of retained data. | `infra/production/object-storage-policies.yaml`, `docs/reliability-and-incident-response-runbook.md` §3, `docs/operations/backup-dr/restore-validation-checklist.md` |
| 17 | incident_response | complete | Incident command roles, severity levels, escalation paths, and per-scenario runbooks are documented and reviewable. | `docs/reliability-and-incident-response-runbook.md` §1,§5,§6, `docs/operations/backup-dr/README.md` |
| 18 | business_continuity_dr | complete | RPO/RTO targets, backup/restore procedures, and a periodic DR drill program with owners are documented. | `docs/reliability-and-incident-response-runbook.md` §2,§3,§4, `docs/operations/backup-dr/playbook-db-restore.md`, `docs/operations/backup-dr/playbook-storage-recovery.md` |
| 19 | performance_capacity | complete | Critical driver-protocol resilience paths have a QA coverage matrix with SLO-oriented production-ready criteria and required telemetry evidence. | `docs/driver-protocol-test-matrix.md`, `backend/tests/test_production_hardening_suite.py` |
| 20 | privacy_compliance | complete | Data classification is documented and mapped to onboarding scope; release readiness gates verify the evidence package before onboarding. | `docs/security/data-classification.md`, `docs/production-hardening/release-gate-evidence.md`, `docs/release-readiness-checklist.md` |
| 21 | change_management | complete | Production promotion is gated on required checks + manual approval, with rollback hook and post-deploy health verification wired into the pipeline. | `.github/workflows/deploy-promotion.yml`, `scripts/deploy_hooks.sh`, `docs/deployment-rollback-runbook.md`, `docs/release-readiness-checklist.md` |

## 2) Integration scope decisions

These three integration areas carry a deliberate in-repo seam. Their disposition
for this release is recorded here so reviewers do not mistake an intentional
boundary for an incomplete control.

### 2.1 SSO (OIDC / SAML) — deferred

- **Disposition:** Deferred. The pluggable identity-provider abstraction exists
  (`IdentityProviderStrategy` protocol, `IdentityProviderRegistry`, and
  `OIDCIdentityProviderStrategy` / `SAMLIdentityProviderStrategy` base hooks in
  `backend/app/security/authn.py`), but `begin_auth` / `complete_auth` raise
  `NotImplementedError` by design — no external IdP is wired for this release.
- **Rationale:** Primary auth (JWT + OTP session) is fully implemented and
  covered by tests; enterprise SSO is a post-MVP onboarding requirement, not a
  release blocker.
- **Re-activation path:** Implement a concrete strategy's `begin_auth` /
  `complete_auth`, register it via `IdentityProviderRegistry.register(...)`, and
  extend `backend/tests/test_authn_identity_providers.py` to cover the live
  exchange. No core auth refactor is required.

### 2.2 TMS / telematics driver mapping — complete

- **Disposition:** Complete. Driver and vehicle identity mapping between ADC and
  external telematics providers is implemented through the `ExternalMapping`
  table, resolved in
  `backend/app/services/telematics_capture_service.py::_resolve_external_mappings`
  (provider `samsara`, `internal_entity_type` of `driver` / `vehicle`, active
  status).
- **Evidence:** `backend/app/db/models.py` (`ExternalMapping`),
  `backend/app/services/telematics_capture_service.py`,
  `backend/app/services/tms_sync_service.py`.

### 2.3 Samsara clip lifecycle — complete

- **Disposition:** Complete. The dashcam clip lifecycle is implemented end to end
  via the capability-provider seam:
  `backend/app/services/samsara_client.py::fetch_dashcam_stream` requests a clip
  (`request_clip`), polls readiness (`fetch_clip_status`), and downloads the
  asset (`download_clip`) only when status is `ready`.
- **Evidence:** `backend/app/services/samsara_client.py`,
  `backend/app/tasks/evidence_tasks.py` (`capture_dashcam`),
  `backend/app/integrations/service.py` (`get_dashcam_provider`).

## 3) Maintenance

- Update this document whenever a Priority-2 control, runbook, or supporting test
  changes, and keep the per-gate `status` here in sync with
  `docs/production-hardening/checklist.yaml`.
- Any change that touches hardening paths must also update
  `docs/production-hardening/control-matrix.md` (enforced by
  `scripts/check_hardening_matrix_updates.py`).
