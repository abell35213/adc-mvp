# Sections 26–28 Readiness Backlog (Sprints 1–5)

This backlog converts Sections 26–28 into an execution plan with explicit ownership, dependencies, estimates, and sprint-level Definition of Done (DoD).

- **Section 26 focus:** diagnostics isolation and export warning fidelity.
- **Section 27 focus:** readiness signal normalization and confidence scoring transparency.
- **Section 28 focus:** guided remediation and operator workflow polish.
- **Section 29 success standard anchor:** deliver outcomes that increase **clarity, confidence, and minimal hand-holding**.

## Planning assumptions

- Sprint length: 2 weeks.
- Estimates use story points (SP) and include implementation + test automation.
- Each sprint must ship user-visible value and improve readiness computation fidelity.

## Sprint backlog

| Sprint | User-visible value shipped | Readiness fidelity advancement | Backend owner (estimate) | Frontend owner (estimate) | QA owner (estimate) | Dependencies | Definition of Done (explicit) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Sprint 1** | New diagnostics panel shows org-scoped evidence health + warning reasons in plain language. | Introduce deterministic readiness-input schema (`missing`, `stale`, `optional_unavailable`) and baseline confidence score v1. | Build normalized diagnostics/readiness input model + API fields (8 SP). | Add diagnostics summary card, warning chips, and “why not ready” tooltip (5 SP). | Add API contract + UI smoke coverage for isolation and warning rendering (3 SP). | Existing diagnostics endpoints, authz scope checks, runtime contract snapshot flow. | 1) Cross-org leakage tests pass. 2) Warning reasons are surfaced in UI for all known failure classes. 3) Readiness score v1 is deterministic for identical inputs. 4) Release note entry created. |
| **Sprint 2** | Incident detail page shows readiness score breakdown by category (evidence, mappings, callbacks, export viability). | Move from single score to weighted category model; add per-category confidence and blocker severity links. | Implement weighted scoring engine + category-level payload and audit event for recompute (8 SP). | Add expandable score breakdown with per-category status badges + blocker links (5 SP). | Add permutation suite for category combinations and regression snapshots (5 SP). | Sprint 1 normalized schema, blocker classifier, audit event plumbing. | 1) Users can see category contributions (not just final status). 2) Backend emits recompute audit event. 3) Weighting config is versioned and test-covered. 4) Zero contract regressions. |
| **Sprint 3** | Guided remediation checklist recommends next-best action and expected readiness impact. | Add confidence calibration using observed resolution outcomes; introduce “projected readiness after fix” calculation. | Add recommendation engine and projected-readiness simulator endpoint (8 SP). | Add remediation checklist UI with projected delta and one-click navigation to required action pages (8 SP). | Add end-to-end scenario tests proving projected status changes after completing fixes (5 SP). | Sprint 2 category payload, action routing paths, historical outcome table. | 1) At least top 5 blocker classes have remediation guidance. 2) Projected readiness is shown before user action. 3) Simulation output matches post-fix recompute in test fixtures. 4) Accessibility checks pass on checklist UI. |
| **Sprint 4** | Real-time readiness timeline in workspace shows what changed, when, and by whom. | Add temporal fidelity: event-driven recompute with reason codes and confidence drift tracking. | Implement recompute event stream + timeline aggregation endpoint (8 SP). | Add timeline component with filters (status change, blocker resolved, confidence drift) (8 SP). | Add latency SLA tests + timeline integrity tests against seeded events (5 SP). | Audit log/event bus availability, incident workspace API stability, Sprint 2/3 event schema. | 1) Timeline updates within SLA target. 2) Every readiness state change has reason code + actor attribution. 3) Confidence drift can be graphed for last 30 days. 4) No orphan timeline events in QA seed runs. |
| **Sprint 5** | Launch-readiness cockpit: consolidated view with confidence trend, blocker burn-down, and export risk forecast. | Final fidelity hardening: multi-signal confidence index with threshold tuning + false-positive/false-negative monitoring. | Ship confidence index v2, threshold tuning controls, and risk forecast endpoint (13 SP). | Ship cockpit page with trend charts, burn-down, and escalation CTA flows (8 SP). | Run launch gate suite + UAT rubric for clarity/confidence/minimal hand-holding (8 SP). | Sprint 1–4 data quality, analytics metrics pipeline, role-based access for cockpit. | 1) Cockpit available to readiness-capable roles. 2) Confidence v2 thresholds are configurable and auditable. 3) UAT meets Section 29 KPI targets. 4) Go-live checklist signed by Backend + Frontend + QA owners. |

## Dependency map (cross-sprint)

1. **Data normalization first (S1) → weighted model (S2) → simulation (S3) → timeline fidelity (S4) → forecasting + tuning (S5)**.
2. **Contract stability gates each sprint**: runtime API contract snapshots updated before UI merge.
3. **QA progression**: unit/API coverage in S1–S2, scenario/e2e in S3–S4, full launch gate in S5.

## Phase KPI targets aligned to Section 29 success standard

Section 29 defines success as **clarity, confidence, minimal hand-holding**. KPI targets below are staged per sprint and must be reviewed at sprint close.

| KPI area | Metric definition | Sprint 1 target | Sprint 2 target | Sprint 3 target | Sprint 4 target | Sprint 5 target (phase exit) |
| --- | --- | --- | --- | --- | --- | --- |
| **Clarity** | % of readiness views where users expand “why not ready” details before taking action (indicates understandable decomposition rather than blind retries). | >= 50% | >= 60% | >= 70% | >= 75% | >= 80% |
| **Clarity** | Median time to identify primary blocker after opening incident workspace. | <= 120 sec | <= 90 sec | <= 75 sec | <= 60 sec | <= 45 sec |
| **Confidence** | Readiness prediction precision against final export outcome. | >= 0.70 | >= 0.78 | >= 0.84 | >= 0.88 | >= 0.92 |
| **Confidence** | False “ready” rate (predicted ready but export fails due to known blocker). | <= 12% | <= 9% | <= 7% | <= 5% | <= 3% |
| **Minimal hand-holding** | % of incidents resolved to export-ready without support escalation. | >= 55% | >= 62% | >= 70% | >= 76% | >= 82% |
| **Minimal hand-holding** | Median admin interventions per incident during readiness remediation. | <= 2.5 | <= 2.1 | <= 1.8 | <= 1.5 | <= 1.2 |

## KPI instrumentation requirements

- Track readiness state transitions, blocker open/resolve events, and recommendation acceptance/rejection reasons.
- Attribute all KPI events by org, incident, actor role, and readiness model version.
- Publish weekly dashboard slices for backend/frontend/QA leads to verify trend direction before sprint close.

## Ownership and governance cadence

- **Backend owner**: model/versioning integrity, API contracts, recompute correctness.
- **Frontend owner**: operator comprehension UX, actionability, and accessibility.
- **QA owner**: fidelity validation, regression confidence, launch-gate evidence.
- **Weekly triad review (Backend + Frontend + QA)**: KPI trend review and dependency risk burndown.
