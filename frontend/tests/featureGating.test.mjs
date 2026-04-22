import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const featureGateSource = readFileSync(new URL('../components/commercial/FeatureGate.tsx', import.meta.url), 'utf8');

test('feature gate supports hide and lock modes with disabled affordance', () => {
  assert.match(featureGateSource, /mode\?:\s*"hide"\s*\|\s*"lock"/);
  assert.match(featureGateSource, /if \(mode === "hide"\) return null/);
  assert.match(featureGateSource, /aria-disabled="true"/);
  assert.match(featureGateSource, /Locked/);
});
