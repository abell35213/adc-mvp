import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const incidentDetailClient = readFileSync(new URL('../app/incidents/[id]/IncidentDetailClient.tsx', import.meta.url), 'utf8');

test('incident detail renders dedicated weather snapshot panel before evidence inventory', () => {
  const weatherPanelIndex = incidentDetailClient.indexOf('Weather snapshot');
  const evidenceInventoryIndex = incidentDetailClient.indexOf('Evidence inventory');
  assert.ok(weatherPanelIndex >= 0, 'weather panel heading should exist');
  assert.ok(evidenceInventoryIndex >= 0, 'evidence inventory heading should exist');
  assert.ok(weatherPanelIndex < evidenceInventoryIndex, 'weather panel should appear before evidence inventory');
});

test('incident detail weather panel includes degraded-state messaging', () => {
  assert.match(incidentDetailClient, /Using last known location/);
  assert.match(incidentDetailClient, /Location unavailable/);
  assert.match(incidentDetailClient, /Weather data unavailable/);
});

test('incident detail weather panel renders normalized metrics and attribution defensively', () => {
  assert.match(incidentDetailClient, /toWeatherMetrics\(weatherConditions\?\.normalized_weather\)/);
  assert.match(incidentDetailClient, /Source: \{formatWeatherValue\(weatherSource\)\}/);
  assert.match(incidentDetailClient, /Captured: \{formatTime\(typeof weatherCapturedAt === "string" \? weatherCapturedAt : null\)\}/);
  assert.match(incidentDetailClient, /weatherMetrics\.length === 0/);
});
