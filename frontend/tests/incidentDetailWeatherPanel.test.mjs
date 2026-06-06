import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const incidentDetailClient = readFileSync(new URL('../app/incidents/[id]/IncidentDetailClient.tsx', import.meta.url), 'utf8');

function assertContains(snippet, message) {
  assert.ok(incidentDetailClient.includes(snippet), message);
}

test('incident detail renders dedicated weather snapshot panel before evidence inventory', () => {
  const weatherPanelIndex = incidentDetailClient.indexOf('Weather snapshot');
  const evidenceInventoryIndex = incidentDetailClient.indexOf('Evidence inventory');
  assert.ok(weatherPanelIndex >= 0, 'weather panel heading should exist');
  assert.ok(evidenceInventoryIndex >= 0, 'evidence inventory heading should exist');
  assert.ok(weatherPanelIndex < evidenceInventoryIndex, 'weather panel should appear before evidence inventory');
});

test('incident detail weather panel renders full weather data attribution', () => {
  assertContains('toWeatherMetrics(weatherConditions?.normalized_weather)', 'normalized weather should be converted into display metrics');
  assertContains('weatherMetrics.map((metric) => (', 'full weather data should render each normalized metric');
  assertContains('Source: {formatWeatherValue(weatherSource)}', 'weather source attribution should be rendered');
  assertContains('Captured: {formatTime(typeof weatherCapturedAt === "string" ? weatherCapturedAt : null)}', 'captured timestamp should be rendered');
});

test('incident detail weather panel supports partial degraded weather data', () => {
  assertContains('weatherLocationSource === "eld_last_known"', 'degraded location source should be detected');
  assertContains('Using last known location', 'degraded location messaging should render');
  assertContains('weatherMetrics.length > 0 ? (', 'partial data should still render available metrics');
});

test('incident detail weather panel handles unavailable weather data', () => {
  assertContains('weatherConditions?.capture_status === "unavailable"', 'unavailable capture status should be detected');
  assertContains('weatherMetrics.length === 0', 'missing metrics should count as unavailable weather');
  assertContains('Weather data unavailable', 'unavailable data messaging should render');
});

test('incident detail weather panel renders unresolved location as Location unavailable', () => {
  assertContains('weatherLocationSource === "unavailable"', 'unresolved location source should be detected');
  assertContains('Location unavailable', 'unresolved location messaging should render');
});
