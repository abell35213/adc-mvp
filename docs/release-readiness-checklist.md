# Release Readiness Checklist

Use this checklist as the final go/no-go gate before a production release.

## Required release gates

- [ ] **All required endpoints deployed**
  - [ ] Backend deployment includes every endpoint required by the release scope.
  - [ ] Endpoint health checks pass in the target environment.
  - [ ] API contract/version verification is complete.
- [ ] **Critical screens implemented and navigable**
  - [ ] All release-critical screens are present in the mobile and web builds.
  - [ ] Navigation paths between critical screens are functional end-to-end.
  - [ ] Blocking UX regressions are resolved or explicitly accepted.
- [ ] **Audit events present**
  - [ ] Required audit events are emitted for all critical user and system actions.
  - [ ] Audit events are queryable in the logging/warehouse destination.
  - [ ] Event payloads include required correlation identifiers.
- [ ] **Analytics events firing**
  - [ ] Release analytics events fire for primary user journeys.
  - [ ] Event properties and naming conform to tracking spec.
  - [ ] Events are visible in the analytics destination.
- [ ] **Security checks passing**
  - [ ] Authentication and authorization checks pass.
  - [ ] Secrets/config checks are complete for target environment.
  - [ ] Vulnerability and dependency checks pass at required severity threshold.
- [ ] **Draft persistence and resume verified**
  - [ ] In-progress drafts persist across app restart/session loss.
  - [ ] Resume flow restores users to the correct step/state.
  - [ ] Edge cases (offline/interrupted session) are validated.
- [ ] **Upload retry reliability verified**
  - [ ] Failed uploads are queued and retried automatically.
  - [ ] Retry/backoff behavior matches expected policy.
  - [ ] Upload eventually succeeds (or fails with actionable surfaced error) under flaky network simulation.


## Production onboarding evidence package

Before customer production onboarding, reviewers must verify:

- `docs/production-hardening/release-gate-evidence.md` is current and references passing tests and controls.
- `docs/security/data-classification.md` is approved and mapped to onboarding scope.
- Priority-1 gate statuses in `docs/production-hardening/checklist.yaml` are set to complete/verified.

## Go/No-Go owner sign-off

Mark one status per owner and include links to evidence.

| Area | Owner | Status (Go / No-Go) | Evidence / Notes |
| --- | --- | --- | --- |
| Mobile |  |  |  |
| Backend |  |  |  |
| QA |  |  |  |
| Product |  |  |  |

## Final release decision

- Release date:
- Release coordinator:
- Final decision: **Go / No-Go**
- Decision timestamp:
- Risks accepted (if any):
