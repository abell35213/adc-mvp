# Phase 5 Case Ops QA Plan (MVP → Production)

## Purpose

This plan defines QA coverage for Case Ops through Phase 5 launch readiness. It maps MVP/production criteria to concrete backend and frontend tests, organizes scenario suites, sequences implementation work by sprint, and defines launch gates and rollback actions.

## Scope

- **In scope:** incident queue/workspace, completeness/readiness scoring, workflow transitions, ownership reassignment, notes/tasks/audit history, stale/overdue alerts, escalation + close/reopen behavior.
- **Out of scope:** driver mobile capture protocol UX and external provider parity beyond existing contract tests.

---

## 1) MVP/Production Criteria → Test Case Mapping

| Criterion | Backend test cases | Frontend test cases | Evidence / status rule |
| --- | --- | --- | --- |
| Org isolation for case data | `backend/tests/test_authorization_regressions.py` (org ownership authz), `backend/tests/test_driver_artifact_routes.py` (driver ownership), `backend/app/core/deps.py` org ownership enforcement path | Add/maintain queue/workspace API fixture tests to ensure cross-org records never render in case-ops views (`frontend/tests/smoke.test.mjs` + incident fixtures) | No endpoint returns cross-org entities for authenticated user role; no UI list/detail leaks foreign-org IDs. |
| Queue correctness (ordering, filtering, summary metrics) | `backend/tests/test_case_ops_workspace_route.py`, `backend/app/db/repo/incidents.py` query sort/filter branches | Add integration-style tests for `IncidentQueueTable` + `IncidentSummaryCards` with readiness/urgency filters | Queue counts match API summary payload and row ordering for each sort mode. |
| Completeness/readiness scoring | `backend/tests/test_case_ops_service.py`, `backend/tests/test_model_improvements.py` (override persistence), `backend/app/case_ops/completeness.py`, `backend/app/case_ops/readiness.py` | Component tests for `CaseReadinessCard`, `MissingItemsPanel`, and detail view state banners | Every backend readiness state is represented with consistent UI label, badge, and action availability. |
| Workflow transition controls | Add transition matrix tests around `backend/app/case_ops/workflow.py` and route-level enforcement in `backend/app/api/routes_incidents.py` | UI tests for `CaseStatusControl` to confirm only allowed actions render and invalid transitions surface errors | Invalid state transitions are rejected server-side and UI cannot silently commit forbidden moves. |
| Ownership reassignment | Validate patch/assignment service behavior in `backend/app/services/incident_ownership_service.py` and incident route tests | UI tests for `CaseOwnerControl` assignment flow (success, permission denied, stale owner) | Assignment updates actor + timestamp + audit event; UI refreshes owner without stale state. |
| Notes/tasks auditability | `backend/tests/test_notes_routes.py`, `backend/tests/test_tasks_routes.py`, `backend/tests/test_audit_service.py`, system event catalog in `backend/tests/test_system_event_types.py` | Component tests for `CaseNotesPanel`, `CaseTasksPanel`, `TimelineFeed` event rendering/order | Create/update/close/delete operations are auditable, immutable in timeline, and actor-attributed. |
| Overdue task accuracy | `backend/tests/test_tasks_routes.py`, overdue repo methods in `backend/app/db/repo/case_tasks.py`, widget route in `backend/app/api/routes/routes_case_ops.py` | Tests for `OverdueFollowUpList` and task widget empty/non-empty states | Overdue = open + due date in past (UTC-safe); UI reflects count and per-task urgency. |
| Stale case alerts | Admin stale threshold logic in `backend/app/api/routes_admin.py`, stale incident tests in `backend/tests/test_driver_admin_endpoints.py` | `AlertsPanel` tests for stale alert ingestion and severity rendering | Alerts fire when stale threshold crossed, clear when case updated/resolved, and severity maps correctly. |
| Export/readiness linkage + close/reopen polish | `backend/app/case_ops/blockers.py`, `backend/tests/test_case_ops_blockers_classifier.py`, close/reopen route tests | Detail-page tests for close/reopen actions, blocker chips, and escalation banners | Closed cases can be reopened with reason, blockers recompute, and export readiness recomputes deterministically. |

---

## 2) Scenario Suite Design

### A. Org isolation suite

1. **Cross-org queue read attempt:** user in Org A queries queue containing Org B incidents.
2. **Cross-org workspace access:** direct incident ID deep link from another org.
3. **Cross-org mutation attempts:** assign owner, add note, add task, transition state.
4. **Role matrix:** investigator/manager/admin across same-org vs foreign-org resources.

**Expected:** 403/404 (by policy), no leaked metadata, no side effects.

### B. Workflow transition control suite

1. Canonical state graph traversal (happy path).
2. Invalid jump attempts (e.g., `not_ready` → `closed` without required completion signals).
3. Concurrent transition race (two actors changing status).
4. Reopen flow with mandatory reason and audit emission.

**Expected:** deterministic transition validation, conflict surfaced, complete audit log.

### C. Ownership reassignment suite

1. Assign unowned case.
2. Reassign owned case.
3. Assign to invalid/inactive user.
4. Unauthorized reassignment by insufficient role.
5. Reassignment while case state changes in parallel.

**Expected:** transactional update, idempotent retries, clear UI error for stale/conflict.

### D. Notes/tasks auditability suite

1. Note create/edit/delete visibility and retention policy checks.
2. Task create/assign/update/complete/reopen.
3. Timeline ordering and actor attribution under same-second events.
4. API/UI parity of timestamps (UTC normalization).

**Expected:** every mutating action has matching audit event and timeline entry.

### E. Completeness/readiness permutations suite

Cover permutations for artifacts/events/exports and manual overrides:

- Missing critical evidence + no export requested.
- Evidence complete + export pending.
- Evidence complete + export complete.
- Manual override set/cleared.
- Blocker present but non-readiness-blocking vs readiness-blocking.

**Expected:** stable completeness percentage, consistent readiness state, and correct missing-items list.

### F. Stale-case + overdue alerts suite

1. Time travel tests around threshold boundaries.
2. Alert deduplication for repeated checks.
3. Severity tuning by age + blocker mix.
4. Escalation triggers and closure behavior.

**Expected:** no flapping at boundaries, tunable severity, explicit close/reopen audit trail.

---

## 3) Sprint-Based QA Implementation Sequence

## Sprint 1 — Queue + Metrics + Core Schema

- Finalize schema assertions and migration integrity checks for queue/readiness fields.
- Add queue API filter/sort contract tests and org isolation baseline tests.
- Add frontend smoke coverage for queue rendering and summary cards.
- Build a QA fixture pack with multi-org incident data and known expected ordering.

**Exit criteria:** queue API deterministic under fixture dataset; baseline isolation tests green.

## Sprint 2 — Workspace + Completeness/Readiness v1

- Expand completeness/readiness backend unit tests for initial scoring model.
- Add workspace route tests for blockers, missing items, and readiness payload.
- Add UI component tests for readiness card, missing items, evidence status panels.
- Validate API/UI enum mapping for readiness states.

**Exit criteria:** workspace detail is functionally complete and state mapping is stable.

## Sprint 3 — Ownership / Workflow / Audit

- Implement transition matrix tests (allow/deny set).
- Add ownership reassignment tests (authz + conflict + idempotency).
- Add audit event assertions for workflow + owner changes.
- Add UI tests for status/owner controls and timeline synchronization.

**Exit criteria:** all mutating case controls emit auditable events and enforce permissions.

## Sprint 4 — Notes / Tasks / Task Widgets

- Expand backend route tests for notes/tasks lifecycle.
- Add overdue widget and "my tasks" query correctness tests.
- Add frontend tests for notes/tasks panels and overdue list behavior.
- Validate timestamp formatting + timezone handling across API and UI.

**Exit criteria:** note/task lifecycle is reliable, auditable, and visible in workspace UX.

## Sprint 5 — Alerts / Severity Tuning / Escalation / Close-Reopen Polish

- Add stale alert threshold + dedupe tests.
- Add escalation flow tests and close/reopen decision-path coverage.
- Add frontend alerts panel tests for severity and resolution states.
- Run end-to-end regression sweep on full scenario suite.

**Exit criteria:** alerting is actionable with low false-positive rate and robust close/reopen handling.

---

## 4) Launch Gates and Rollback Plan

## Launch gates (must pass)

1. **Coverage gate:** each criterion row above has at least one passing backend test and one passing frontend test (or documented N/A approved by QA + Eng).
2. **Isolation/security gate:** zero open P0/P1 authz findings for org boundaries and ownership changes.
3. **Workflow integrity gate:** invalid transition attempts rejected in API and reflected in UI.
4. **Auditability gate:** notes/tasks/ownership/workflow mutations produce queryable audit events with actor + timestamp.
5. **Alert quality gate:** stale/overdue alert precision validated against gold dataset; false-positive and false-negative rates within agreed tolerance.
6. **Operational gate:** dashboards and runbooks updated for incident triage and escalation response.

## Rollback plan

### Triggers

- Elevated 5xx or mutation error rates after rollout.
- Cross-org access leak or authorization regression.
- Alert flood causing operator overload.
- Workflow dead-ends (cases stuck due to transition bug).

### Rollback actions

1. **Feature flag fallback:** disable case-ops mutation controls (owner/workflow/notes/tasks write paths) while retaining read-only queue/workspace.
2. **Alert throttle:** raise stale/overdue thresholds and disable escalation fan-out until tuning patch ships.
3. **UI rollback:** redeploy previous frontend release with safe controls hidden.
4. **Backend rollback:** redeploy prior backend image and, if needed, run prevalidated migration rollback script for non-destructive schema deltas.
5. **Data remediation:** run audit log review + targeted repair scripts for partial writes from failed transitions.

### Recovery and re-enable checklist

- Confirm rollback metrics normalize.
- Execute focused regression pack on root-cause area.
- Publish incident summary and corrective actions.
- Re-enable features progressively (queue read-only → mutations → alerts/escalation).

---

## Execution Cadence and Reporting

- **Daily:** sprint QA status, failing test triage, blocker aging.
- **Twice weekly:** cross-functional review (QA + backend + frontend + product) on gate readiness.
- **Pre-launch:** freeze window regression + sign-off recorded in release checklist and gate evidence docs.
