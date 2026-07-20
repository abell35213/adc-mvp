import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');
const model = read('lib/exportDocuments.ts');
const page = read('app/exports/page.tsx');
const list = read('components/exports/DocumentExportList.tsx');
const incident = read('components/exports/IncidentDetailExportPanel.tsx');
const generateModal = read('components/exports/GenerateExportModal.tsx');
const primitives = read('components/ui/Misc.tsx');
const buttons = read('components/ui/Button.tsx');
const cards = read('components/ui/Card.tsx');
const { countExportQuickFilters, filterExportDocuments, matchesExportQuickFilter, startOfCurrentWeek } = await import('../lib/exportQuickFilters.mjs');

test('export document view model centralizes readable labels, status, stage, actions, and safe failures', () => {
  for (const snippet of ['EXPORT_TYPE_LABELS', 'Legal Defense Packet', 'Insurance Notice', 'EXPORT_STAGE_LABELS', 'EXPORT_STATUS_COPY', 'safeFailureReason', 'missingRequirements', 'canDownload', 'canRetry', 'canRegenerate', 'technicalIdLabel', 'sortExportDocuments']) assert.match(model, new RegExp(snippet));
  assert.match(model, /traceback\|exception\|sql\|stack\|s3\|aws\|credential\|password\|secret/i);
});

test('global exports page uses shared primitives, metrics, filters, details, and raw-id disclosure', () => {
  for (const snippet of ['Exports &amp; Documents', 'Generate, monitor, and download defense-ready case materials', 'MetricCard', 'Ready to Download', 'Needs Attention', 'DocumentExportList', 'Drawer', 'Technical details', 'Clear filters']) assert.match(page, new RegExp(snippet));
});

test('export metric filters use real status groups and compose with search', () => {
  const now = new Date('2026-07-22T12:00:00Z');
  const items = [
    { id: 'ready', status: 'ready', completed_at_utc: '2026-07-21T09:00:00Z', searchText: 'alpha packet' },
    { id: 'old-ready', status: 'ready', completed_at_utc: '2026-07-12T09:00:00Z', searchText: 'beta packet' },
    { id: 'requested', status: 'requested', searchText: 'alpha notice' },
    { id: 'queued', status: 'queued', searchText: 'beta notice' },
    { id: 'processing', status: 'processing', searchText: 'gamma notice' },
    { id: 'failed', status: 'failed', searchText: 'alpha review' },
    { id: 'expired', status: 'expired', completed_at_utc: '2026-07-21T09:00:00Z', searchText: 'beta review' },
  ];
  assert.deepEqual(filterExportDocuments(items, { quickFilter: 'ready', now }).map((item) => item.id), ['ready', 'old-ready']);
  assert.deepEqual(filterExportDocuments(items, { quickFilter: 'generating', now }).map((item) => item.id), ['requested', 'queued', 'processing']);
  assert.deepEqual(filterExportDocuments(items, { quickFilter: 'attention', now }).map((item) => item.id), ['failed', 'expired']);
  assert.deepEqual(filterExportDocuments(items, { quickFilter: 'generating', query: 'beta', now }).map((item) => item.id), ['queued']);
  assert.deepEqual(countExportQuickFilters(items, now), { ready: 2, generating: 3, attention: 2, completedThisWeek: 1 });
});

test('completed this week uses ready completion timestamps and calendar-week boundaries', () => {
  const now = new Date('2026-07-22T12:00:00Z');
  assert.equal(startOfCurrentWeek(now).toISOString(), '2026-07-20T00:00:00.000Z');
  assert.equal(matchesExportQuickFilter({ status: 'ready', created_at_utc: '2026-07-21T09:00:00Z' }, 'completedThisWeek', now), false);
  assert.equal(matchesExportQuickFilter({ status: 'expired', completed_at_utc: '2026-07-21T09:00:00Z' }, 'completedThisWeek', now), false);
  assert.equal(matchesExportQuickFilter({ status: 'ready', completed_at_utc: '2026-07-20T00:00:00Z' }, 'completedThisWeek', now), true);
});

test('quick-filter cards expose selected semantics, URL state, and clearing', () => {
  assert.match(page, /pressed=\{quickFilter === "ready"\}/);
  assert.match(page, /quick=|params\.set\("quick"/);
  assert.match(page, /setQuickFilter\(null\)/);
  assert.match(page, /filterExportDocuments/);
  assert.match(page, /role="status"/);
  assert.match(primitives, /aria-pressed=\{pressed\}/);
});

test('shared interactive primitives distinguish pointer, disabled, and static cards', () => {
  assert.match(buttons, /cursor-pointer/);
  assert.match(buttons, /disabled/);
  assert.match(primitives, /cursor-pointer/);
  assert.match(primitives, /disabled:cursor-not-allowed/);
  assert.doesNotMatch(cards, /cursor-pointer|cursor-not-allowed/);
});

test('document list provides table and mobile cards with human-readable actions', () => {
  for (const snippet of ['caption="Exports and documents"', 'Document', 'Case', 'Progress / Stage', 'Requested By', 'md:hidden', 'Download', 'Review issue', 'Copy export ID', 'Copy case ID']) assert.match(list, new RegExp(snippet));
  assert.doesNotMatch(list, /package_sha256.*<p className="font-mono/);
});

test('incident documents tab shares the document list and action language', () => {
  for (const snippet of ['DocumentExportList', 'Generate Document', 'Document generation is in progress', 'Defense document is ready', 'Document could not be generated', 'No documents for this case']) assert.match(incident, new RegExp(snippet));
});


test('generate export modal uses shared primitives and safe workflow copy', () => {
  for (const snippet of ['Modal', 'FormField', 'Select', 'StatusBadge', 'Alert', 'EmptyState', 'Generate document', 'Selected incident', 'Readiness', 'What happens next']) assert.match(generateModal, new RegExp(snippet));
  assert.ok(generateModal.includes('if (disabled) return'));
  assert.doesNotMatch(generateModal, /bg-blue-600|bg-amber-50|text-amber-900|<button/);
  assert.doesNotMatch(generateModal, />court_defense<|>insurer_packet<|>internal_review<|>compliance_audit</);
});
