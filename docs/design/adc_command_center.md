# ADC Command Center Dashboard

## 1. Purpose
The Incident Command Center is the authenticated dashboard for triaging active accident-defense cases. Within a few seconds it should answer: active case volume, action-required volume, export-ready volume, overdue work, the first case to open, and the next best action.

## 2. Information hierarchy
The page uses this hierarchy: shared page header, four primary operational metrics, compact filters, dominant Priority Case Queue, and a secondary Needs Attention panel. Onboarding and demo-tour affordances are subordinate to case operations.

## 3. Metric definitions
- **Active Cases**: backend `open_incidents` when available; otherwise loaded queue items whose case status is not terminal (`closed`).
- **Need Action**: backend `blocked_incidents` when available; otherwise loaded cases with critical/important blockers, escalated status, awaiting-evidence status, or blocked/not-ready readiness.
- **Ready for Export**: loaded cases with `case_status=ready_for_export`, `readiness_state=ready_for_export`, or `readiness_state=ready`.
- **Overdue**: backend `overdue_tasks` when available; otherwise loaded non-completed tasks with due dates before the current time.

No trend is shown because the dashboard API does not currently provide comparison-period data.

## 4. Priority ordering rules
The frontend sorts the loaded queue deterministically when the backend returns queue data. Priority score considers, in order: critical blockers or escalated status, blocked/not-ready readiness, important blockers, awaiting-evidence status, unassigned ownership, lower completeness, and most recent activity as a tie-breaker. This preserves existing API filtering and updates while making the visible queue operationally decisive.

## 5. Queue column rules
Desktop columns are Case, Incident, Status, Readiness, Owner, Updated, and Actions. Mobile renders equivalent case cards to avoid horizontal workflow scrolling. Status is rendered with `StatusBadge`; readiness uses `ProgressBar`; updated time includes relative text with an absolute timestamp on the `time` element.

## 6. Human-readable identifier strategy
The queue response currently exposes `incident_id`, `adc_vehicle_id`, `adc_driver_id`, owner user ID, severity, timestamps, readiness, status, completeness, and blocker counts. It does not expose a human-readable case number, driver name, owner name, vehicle label/unit, incident title, incident location, or incident type. Phase 3 therefore de-emphasizes the raw UUID by showing a short fallback case label (`Case {first 8 characters}`) and keeps the full ID available through secondary row actions/tooltips.

## 7. Filter behavior
Filters preserve existing server-side behavior for search, status, readiness, blockers, and sort. Search is limited to fields supported by the existing queue API; the frontend does not imply searching unloaded records. Active filter count appears on Clear filters.

## 8. Needs Attention behavior
Needs Attention summarizes supported categories: critical blockers/escalations, missing evidence or blocked readiness, overdue follow-ups, unassigned cases, export-ready/aging cases, and stalled cases. Items link by applying existing queue filters rather than duplicating another table.

## 9. Demo-tour behavior
The demo tour remains driven by `?demo=1`, preserves URL state during filter updates, and remains dismissible. The visual treatment is a compact alert with a primary action to open the priority incident plus secondary demo destinations.

## 10. Responsive behavior
At desktop widths the dashboard uses four metrics, a wide queue, and a narrower attention rail. At tablet widths metrics wrap and the attention rail stacks below as space requires. At mobile widths the table is replaced by case cards with the same core information and actions.

## 11. Accessibility behavior
The page uses a single shared page header, labeled metric region, accessible filter labels, a table caption (`Priority cases`), explicit Open case buttons, semantic progress bars with numeric values, readable status text, keyboard-accessible primitive controls, and non-color-only status labels.

## 12. Legacy dashboard components migrated
Phase 3 migrated dashboard usage from legacy/local patterns toward `Button`, `Badge`, `StatusBadge`, `Card`, `MetricCard`, `PageHeader`, `ProgressBar`, `Avatar`, `DropdownMenu`, `Input`, `Select`, `EmptyState`, `Skeleton`, `Alert`, and the table foundation.

## 13. Remaining Phase 4 dependencies
Incident detail, evidence detail, exports/documents detail, reports, vehicles, settings, and administration still contain legacy surface-specific styling. Product data gaps remain: human-readable case numbers, owner names, driver names, vehicle/unit labels, incident location, incident type, and export workflow summaries should be added to backend contracts before later dashboard refinements.
