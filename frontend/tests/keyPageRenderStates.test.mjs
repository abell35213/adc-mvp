import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const deploymentPage = readFileSync(new URL('../app/deployment/page.tsx', import.meta.url), 'utf8');
const trustPage = readFileSync(new URL('../app/trust/page.tsx', import.meta.url), 'utf8');

test('deployment page renders readiness banner and region coverage cards', () => {
  assert.match(deploymentPage, /MainLayout title="Deployment Coverage"/);
  assert.match(deploymentPage, /ExpansionReadinessBanner/);
  assert.match(deploymentPage, /DeploymentCoverageCard region="US West"/);
  assert.match(deploymentPage, /DeploymentCoverageCard region="Canada"/);
});

test('trust page renders trust center layout and core trust sections', () => {
  assert.match(trustPage, /MainLayout title="Trust Center"/);
  assert.match(trustPage, /TrustSectionCard/);
  assert.match(trustPage, /title="Security controls"/);
  assert.match(trustPage, /title="Compliance evidence"/);
});
