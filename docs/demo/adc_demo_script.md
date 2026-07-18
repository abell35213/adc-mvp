# Five-to-ten-minute ADC demo script

## 1. Log in

Open `http://localhost:3000/login?demo=1` and sign in with `demo-admin@adc.local` / `DemoAdmin!2345`.

Talking point: this is a deterministic fictional tenant, safe to reset and re-seed for screenshots or pilot walkthroughs.

## 2. Command Center metrics

Show the Incident Command Center summary cards. Expected state: nonzero active cases, need-action count, ready-for-export cases, and overdue tasks.

Talking point: operations can immediately see workload density instead of landing in an empty development database.

## 3. Needs Attention

Review Needs Attention. Expected state: a mix of stalled, unassigned, blocked, overdue, and export-aging signals.

Talking point: the dashboard is calculated from incident readiness, assignments, export age, and task due dates rather than hard-coded demo numbers.

## 4. Open featured collision

Open `ADC-DEMO-2026-001` — the serious commercial tractor-trailer collision near Braselton, Georgia.

Expected state: escalated/high-severity case, assigned owner, incomplete readiness, pending police report, captured scene/driver/video evidence, overdue follow-up, and export activity.

## 5. Explain readiness and missing evidence

Use the overview/readiness section to explain why the case is not fully ready: critical evidence is still pending and an urgent follow-up task is overdue.

## 6. Review Evidence

Open Evidence for `ADC-DEMO-2026-001`. Expected state: multiple evidence cards across captured, pending, and unavailable-style states.

Talking point: the workflow distinguishes received artifacts from outstanding requests.

## 7. Review Timeline

Open Timeline. Expected state: a chronological story with incident creation, assignment, evidence requests, evidence receipts, notes, tasks, readiness recalculation, and export activity.

## 8. Review Activity/tasks

Open Activity or Tasks/Notes. Expected state: open, blocked, overdue, and completed tasks plus professional notes.

Talking point: claims, safety, fleet, and legal operations all have clear next actions.

## 9. Review Documents

Open Documents for the featured collision. Expected state: export/document rows across queued, processing, ready, and/or failed operational states.

Backup path: if live document generation or download is unavailable in the local environment, use the existing ready seeded export metadata and explain that download requires configured local artifact storage.

## 10. Open global Exports

Navigate to global Exports. Expected state: several statuses are visible, including ready, requested/queued, processing, failed, expired, and a retry relationship.

## 11. Show cargo theft

Open `ADC-DEMO-2026-002` — cargo theft at a Memphis cross-dock.

Talking point: the case demonstrates cargo-document gaps such as bill of lading and inventory evidence, insurance documentation, agency notification, and ongoing export workflow.

## 12. End with nearly complete case

Open `ADC-DEMO-2026-003` — minor property damage at a Jacksonville receiver.

Talking point: contrast this nearly complete case with the escalated collision. It should show high readiness, mostly complete evidence, mostly completed tasks, and a ready defense document.
