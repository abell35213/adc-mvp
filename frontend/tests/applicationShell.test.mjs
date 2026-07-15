import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');

test('application shell exposes landmarks, skip link, primary action, and consolidated components', () => {
  const shell = read('components/app-shell/AppShell.tsx');
  assert.match(shell, /href="#main-content"/);
  assert.match(shell, /<Sidebar/);
  assert.match(shell, /<TopBar/);
  assert.match(shell, /<PageContainer/);
  assert.match(read('components/app-shell/PageContainer.tsx'), /<main id="main-content"/);
  assert.match(read('components/app-shell/TopBar.tsx'), /Create Incident/);
});

test('navigation hierarchy uses authorized existing routes and active route state', () => {
  const nav = read('components/app-shell/navigation.ts');
  for (const label of ['Command Center', 'Cases', 'Evidence', 'Exports', 'Vehicles', 'Reports', 'Settings', 'Help', 'Administration']) assert.match(nav, new RegExp(label));
  assert.match(nav, /hasRoleCapability\(role, "vehicle_qr:write"\)/);
  assert.match(nav, /hasRoleCapability\(role, "vehicle_qr:read"\)/);
  assert.match(read('components/app-shell/NavigationItem.tsx'), /aria-current=\{active \? "page"/);
});

test('organization context avoids displaying UUIDs as primary visible context', () => {
  const nav = read('components/app-shell/navigation.ts');
  assert.match(nav, /getOrganizationLabel/);
  assert.match(nav, /\^\[a-f0-9-\]\{20,\}\$/);
  assert.match(nav, /Primary organization/);
});

test('user menu supports open close semantics and sign out action', () => {
  const menu = read('components/app-shell/UserMenu.tsx');
  assert.match(menu, /aria-haspopup="menu"/);
  assert.match(menu, /Escape/);
  assert.match(menu, /role="menuitem"/);
  assert.match(menu, /logout\(\)/);
});

test('mobile navigation uses drawer, focus return capable trigger, active route and no duplicate nav labels', () => {
  const mobile = read('components/app-shell/MobileNavigation.tsx');
  assert.match(mobile, /<Drawer/);
  assert.match(mobile, /Open navigation menu/);
  assert.match(mobile, /aria-label="Mobile navigation"/);
  assert.doesNotMatch(mobile, /aria-label="Primary navigation"/);
  assert.match(mobile, /Create Incident/);
});
