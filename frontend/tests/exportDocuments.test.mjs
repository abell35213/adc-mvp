import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');
const model = read('lib/exportDocuments.ts');
const page = read('app/exports/page.tsx');
const list = read('components/exports/DocumentExportList.tsx');
const incident = read('components/exports/IncidentDetailExportPanel.tsx');

test('export document view model centralizes readable labels, status, stage, actions, and safe failures', () => {
  for (const snippet of ['EXPORT_TYPE_LABELS', 'Legal Defense Packet', 'Insurance Notice', 'EXPORT_STAGE_LABELS', 'EXPORT_STATUS_COPY', 'safeFailureReason', 'missingRequirements', 'canDownload', 'canRetry', 'canRegenerate', 'technicalIdLabel', 'sortExportDocuments']) assert.match(model, new RegExp(snippet));
  assert.match(model, /traceback\|exception\|sql\|stack\|s3\|aws\|credential\|password\|secret/i);
});

test('global exports page uses shared primitives, metrics, filters, details, and raw-id disclosure', () => {
  for (const snippet of ['Exports &amp; Documents', 'Generate, monitor, and download defense-ready case materials', 'MetricCard', 'Ready to Download', 'Needs Attention', 'DocumentExportList', 'Drawer', 'Technical details', 'Clear filters']) assert.match(page, new RegExp(snippet));
});

test('document list provides table and mobile cards with human-readable actions', () => {
  for (const snippet of ['caption="Exports and documents"', 'Document', 'Case', 'Progress / Stage', 'Requested By', 'md:hidden', 'Download', 'Review issue', 'Copy export ID', 'Copy case ID']) assert.match(list, new RegExp(snippet));
  assert.doesNotMatch(list, /package_sha256.*<p className="font-mono/);
});

test('incident documents tab shares the document list and action language', () => {
  for (const snippet of ['DocumentExportList', 'Generate Document', 'Document generation is in progress', 'Defense document is ready', 'Document could not be generated', 'No documents for this case']) assert.match(incident, new RegExp(snippet));
});
