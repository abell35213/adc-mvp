# ADC Incident Workspace

## 1. Workspace purpose
The incident workspace is the premium case surface for understanding one accident-defense case, its readiness, missing information, available evidence, generated documents, and recent collaboration.

## 2. Information hierarchy
The page uses the Phase 2 application shell, a structured case header, restrained tabs, primary content, and a desktop action rail. The header answers case reference, title/type, status, date/time, location, owner, last update, readiness, and next action before detailed tabs.

## 3. Incident display-field strategy
The detail API currently returns incident ID, status, severity, vehicle identifiers, driver identifier, creation time, evidence, exports, timeline, weather, readiness, missing items, and blockers. It does not return authoritative human-readable case number, owner display name beyond workspace email, driver name, vehicle unit label beyond existing IDs, incident location, or incident type/title. The frontend therefore centralizes restrained fallbacks in `frontend/lib/incident-workspace/viewModel.ts` and keeps technical identifiers secondary.

## 4. Case-reference fallback rules
Until an authoritative case number exists, the workspace displays `Case {first 8 uppercase incident ID characters}`. The full incident UUID remains available through Copy case ID and View technical details.

## 5. Tab responsibilities
Tabs are Overview, Evidence, Timeline, Documents, and Activity. The selected tab is preserved in the `tab` query parameter for direct-link behavior.

## 6. Overview structure
Overview summarizes incident narrative, driver and vehicle, weather snapshot, evidence inventory guidance, blockers, missing information, and recommended next action without duplicating all evidence rows or document rows.

## 7. Evidence grouping
Evidence is grouped by the currently supported ADC artifact inventory. Captured, pending, and unavailable states are mapped to shared status badges and readable cards.

## 8. Timeline behavior
Timeline combines incident event data and workspace activity where available, sorts newest first deterministically, and hides raw payload JSON behind View technical details disclosures.

## 9. Documents behavior
Documents remain backed by the existing export workflow. The Documents tab now uses the shared export document view model and shared document list so generation, status/stage language, retry, download, safe failure messaging, and technical details match the global Exports & Documents page while staying scoped to the current incident.

## 10. Activity behavior
Activity is reserved for human collaboration and case-level tasks/notes. System events belong in Timeline. Notes and tasks keep existing create/complete mutations.

## 11. Next-best-action rules
The view model prefers ready packet download, then critical blockers, then missing evidence, then packet generation when readiness is ready, then a stable Update case fallback.

## 12. Action-rail behavior
Desktop uses a sticky action rail with Next Best Action, Missing Items, owner assignment, status control, and collapsed technical details. Tablet and mobile stack this content inline below the tab content without hidden critical blockers.

## 13. Responsive behavior
The layout uses a single content column until extra-large widths, then adds a narrow sticky action rail. Evidence items and activity entries are cards that stack naturally on small screens.

## 14. Accessibility behavior
The page has one h1 in the case header, shared Tabs semantics, progressbar semantics, status labels with text, timeline as an ordered list, keyboard-reachable disclosures for technical details, and explicit action labels.

## 15. Backend contract changes
No backend response-contract changes were made in Phase 4. Desired authoritative display fields remain future backend work: `case_reference`, `owner_display_name`, `driver_display_name`, `vehicle_display_label`, `incident_location_display`, and `incident_type_display`.

## 16. Demo-seed changes
No demo seed changes were made. The workspace uses existing deterministic incident, workspace, evidence, export, timeline, note, and task records.

## 17. Legacy components migrated
Incident detail now uses the Phase 2 shell and Phase 1 primitives: Button, StatusBadge, Card, Tabs, ProgressBar, DropdownMenu, Alert, EmptyState, and Skeleton. The legacy raw CaseHeroHeader, EvidenceStatusPanel, TimelineFeed, MissingItemsPanel, CaseReadinessCard, CaseTasksPanel, CaseNotesPanel, and StickySidebar are no longer composed by the incident detail route.

## 18. Remaining Phase 5 dependencies
Remaining dependencies are authoritative human-readable incident fields, richer document metadata, explicit preview availability, explicit regenerate support, richer evidence source/uploader metadata, a more complete permission-aware secondary action menu, and broader legacy component cleanup outside incident detail.
