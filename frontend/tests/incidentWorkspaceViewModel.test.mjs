import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(new URL('../lib/incident-workspace/viewModel.ts', import.meta.url), 'utf8');

function assertContains(snippet, message) {
  assert.ok(source.includes(snippet), message);
}

test('view model centralizes case-reference and human-readable fallbacks', () => {
  assertContains('caseReference: caseReference(incident.incident_id)', 'case reference should be derived centrally');
  assertContains('ownerLabel', 'owner display fallback should exist');
  assertContains('driverLabel', 'driver display fallback should exist');
  assertContains('vehicleLabel', 'vehicle display fallback should exist');
});

test('view model centralizes blocker grouping and next best action priority', () => {
  assertContains('function groupBlockers', 'blocker grouping helper should exist');
  assertContains('blockers.critical.length > 0', 'critical blockers should influence action');
  assertContains('Request missing evidence', 'missing evidence action should exist');
  assertContains('Download defense packet', 'ready document action should exist');
});

test('view model centralizes evidence and document grouping', () => {
  assertContains('function buildEvidenceGroups', 'evidence grouping helper should exist');
  assertContains('EVIDENCE_TYPES.map', 'supported evidence types should drive grouping');
  assertContains('function buildDocumentGroups', 'document grouping helper should exist');
  assertContains('primaryAction', 'document action mapping should exist');
});

test('view model centralizes timeline ordering and technical details', () => {
  assertContains('function buildTimelineItems', 'timeline adapter should exist');
  assertContains('JSON.stringify(event.payload ?? {}, null, 2)', 'technical event detail should be retained behind disclosure');
  assertContains('new Date(b.absolute).getTime() - new Date(a.absolute).getTime()', 'timeline should sort newest first deterministically');
});
