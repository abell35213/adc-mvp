import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');
const dashboard = read('app/dashboard/DashboardClient.tsx');
const table = read('components/case-ops/IncidentQueueTable.tsx');
const filter = read('components/case-ops/IncidentFilterBar.tsx');
const model = read('lib/commandCenter.ts');

test('dashboard uses shared header, primary action, and four command metrics', () => {
  assert.match(dashboard, /Incident Command Center/);
  assert.match(dashboard, /Monitor active cases, resolve blockers, and prepare defense-ready records/);
  assert.match(dashboard, /Create Incident/);
  for (const label of ['Active Cases', 'Need Action', 'Ready for Export', 'Overdue']) assert.match(dashboard, new RegExp(label));
  assert.doesNotMatch(dashboard, /trend=/);
});

test('command center model documents operational calculations and priority ordering', () => {
  for (const fn of ['buildOperationalMetrics', 'sortPriorityCases', 'priorityScore', 'buildAttentionItems']) assert.match(model, new RegExp(`function ${fn}`));
  assert.match(model, /TERMINAL_STATUSES/);
  assert.match(model, /blocked_incidents/);
  assert.match(model, /ready_for_export/);
  assert.match(model, /overdue_tasks/);
  assert.match(model, /blockers\.critical/);
  assert.match(model, /owner_user_id/);
});

test('priority queue de-emphasizes raw ids and moves secondary row actions into menu', () => {
  assert.match(table, /caption="Priority cases"/);
  for (const heading of ['Case', 'Incident', 'Status', 'Readiness', 'Owner', 'Updated', 'Actions']) assert.match(table, new RegExp(heading));
  assert.match(table, /caseLabel\(item\)/);
  assert.match(table, /Technical ID available in actions/);
  assert.match(table, /Open case/);
  assert.match(table, /DropdownMenu/);
  assert.doesNotMatch(table, /<select/);
  assert.match(table, /md:hidden/);
});

test('filters and needs attention support required dashboard actions', () => {
  for (const label of ['Search', 'Status', 'Readiness', 'Blockers', 'Sort', 'Clear filters']) assert.match(filter, new RegExp(label));
  for (const category of ['Critical blockers', 'Missing evidence', 'Overdue follow-ups', 'Unassigned cases', 'Ready for export', 'Stalled cases']) assert.match(model, new RegExp(category));
  for (const mapping of ['blockers: "critical"', 'status: "awaiting_evidence"', 'status: "ready_for_export"']) assert.match(model, new RegExp(mapping));
  assert.match(dashboard, /aria-pressed=\{active\}/);
  assert.match(dashboard, /item\.filter && item\.count > 0/);
  assert.match(dashboard, /isAttentionFilterActive/);
  assert.match(dashboard, /scrollIntoView/);
  assert.match(dashboard, /role="status"/);
  assert.match(dashboard, /filter applied/);
  assert.match(dashboard, /filter cleared/);
  assert.match(dashboard, /<button type="button"/);
  assert.match(dashboard, /cursor-pointer/);
  assert.match(dashboard, /aria-disabled="true"/);
});

test('attention filters use the canonical queue URL fields and replace conflicting filters', () => {
  assert.match(dashboard, /status: "", readiness_state: "", blockers: ""/);
  for (const query of ['status', 'readiness_state', 'blockers']) assert.match(dashboard, new RegExp(`query\\.set\\("${query}"`));
  assert.match(dashboard, /updateFilters\(next\)/);
  assert.match(dashboard, /getIncidentQueue\(\{ \.\.\.buildQueueParams\(filters\)/);
});

test('demo tour remains compact, dismissible, and preserves demo routing', () => {
  assert.match(dashboard, /data-testid="demo-tour-banner"/);
  assert.match(dashboard, /Demo Tour · Step 1 of 4/);
  assert.match(dashboard, /Open priority incident/);
  assert.match(dashboard, /setDemoTourDismissed\(true\)/);
  assert.match(dashboard, /if \(isDemoMode\) query\.set\("demo", "1"\)/);
});


test('dashboard never requests unsupported page sizes and isolates partial failures', () => {
  assert.doesNotMatch(dashboard, /page_size:\s*500|QUEUE_ALL_PAGE_SIZE\s*=\s*500/);
  assert.match(dashboard, /const QUEUE_ALL_PAGE_SIZE = 100/);
  assert.match(dashboard, /Promise\.allSettled\(\[getIncidentQueue/);
  assert.match(dashboard, /Promise\.allSettled\(\[getIncidentSummaryMetrics/);
});

test('dashboard provides non-null loading shell and valid alert heading order', () => {
  const page = read('app/dashboard/page.tsx');
  assert.doesNotMatch(page, /fallback=\{null\}/);
  assert.match(page, /Loading command center/);
  assert.match(dashboard, /titleAs="h2" title="Command center partially unavailable"/);
});
