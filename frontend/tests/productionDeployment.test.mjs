import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const nextConfigSource = readFileSync(new URL('../next.config.mjs', import.meta.url), 'utf8');
const incidentDetailPageSource = readFileSync(new URL('../app/incidents/[id]/page.tsx', import.meta.url), 'utf8');
const apiCoreSource = readFileSync(new URL('../lib/api/core.ts', import.meta.url), 'utf8');

test('Next.js production config uses dynamic app mode and preserves image compatibility', () => {
  assert.doesNotMatch(nextConfigSource, /output:\s*["']export["']/);
  assert.match(nextConfigSource, /images:\s*{[\s\S]*unoptimized:\s*true[\s\S]*}/);
});

test('Next.js production config limits build worker parallelism for constrained CI', () => {
  assert.match(nextConfigSource, /experimental:\s*{[\s\S]*cpus:\s*1[\s\S]*}/);
});

test('incident detail page does not rely on placeholder static params', () => {
  assert.doesNotMatch(incidentDetailPageSource, /generateStaticParams/);
  assert.doesNotMatch(incidentDetailPageSource, /placeholder/);
  assert.match(incidentDetailPageSource, /<IncidentDetailClient\s*\/>/);
});

test('API base URL resolution keeps internal server and public browser env handling', () => {
  assert.match(apiCoreSource, /typeof window === "undefined"/);
  assert.match(apiCoreSource, /process\.env\.API_INTERNAL_BASE_URL\s*\?\?/);
  assert.match(apiCoreSource, /process\.env\.NEXT_PUBLIC_API_BASE_URL\s*\?\?/);
  assert.match(apiCoreSource, /"http:\/\/localhost:8000"/);
});
