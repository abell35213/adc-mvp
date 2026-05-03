import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const loginPage = readFileSync(new URL('../app/login/page.tsx', import.meta.url), 'utf8');
const heroComponent = readFileSync(new URL('../components/marketing/Hero.tsx', import.meta.url), 'utf8');
const demoSection = readFileSync(new URL('../components/marketing/DemoSection.tsx', import.meta.url), 'utf8');
const dashboardClient = readFileSync(
  new URL('../app/dashboard/DashboardClient.tsx', import.meta.url),
  'utf8',
);
const envExample = readFileSync(new URL('../../.env.example', import.meta.url), 'utf8');

test('login page reads ?demo=1 and prefills credentials only in demo mode', () => {
  // Reads search params via Next's hook.
  assert.match(loginPage, /useSearchParams/);
  // Branches on the "demo" query param value.
  assert.match(loginPage, /searchParams\?\.get\("demo"\) === "1"/);
  // Prefill is gated on the resolved demo-mode flag — bail out early when off.
  assert.match(loginPage, /if \(!isDemoMode\) return;/);
  // Sources the demo credentials from public env vars.
  assert.match(loginPage, /NEXT_PUBLIC_DEMO_EMAIL/);
  assert.match(loginPage, /NEXT_PUBLIC_DEMO_PASSWORD/);
  // Sandbox banner is rendered when in demo mode.
  assert.match(loginPage, /data-testid="demo-sandbox-banner"/);
  assert.match(loginPage, /demo sandbox/i);
});

test('login page never renders the sandbox banner outside demo mode', () => {
  // The banner must be wrapped in an isDemoMode guard.
  const bannerMatch = loginPage.match(/\{isDemoMode && \(\s*<div[\s\S]*?demo-sandbox-banner[\s\S]*?<\/div>\s*\)\}/);
  assert.ok(bannerMatch, 'sandbox banner JSX must be guarded by isDemoMode');
});

test('login page does not embed any plaintext demo credential fallback', () => {
  // Security: the client bundle must not ship hard-coded demo creds — gating
  // demo mode requires the operator to explicitly set NEXT_PUBLIC_DEMO_*.
  assert.doesNotMatch(loginPage, /DemoAdmin!2345/);
  assert.doesNotMatch(loginPage, /demo-admin@adc\.local/);
  assert.doesNotMatch(loginPage, /DEMO_PASSWORD_FALLBACK/);
  assert.doesNotMatch(loginPage, /DEMO_EMAIL_FALLBACK/);
});

test('login demo mode is gated on env vars and non-production builds', () => {
  // Both env vars must be set, AND the build must not be production.
  assert.match(loginPage, /process\.env\.NODE_ENV !== "production"/);
  assert.match(loginPage, /Boolean\(DEMO_EMAIL_ENV\)/);
  assert.match(loginPage, /Boolean\(DEMO_PASSWORD_ENV\)/);
  // The query-string flag alone is not sufficient; it must AND the resolved
  // DEMO_PREFILL_ENABLED constant.
  assert.match(loginPage, /isDemoRequest && DEMO_PREFILL_ENABLED/);
});

test('Hero header exposes Login, Check our Prices, and Book a Demo links with the correct routes', () => {
  // The standalone "Login" link is present so existing users can sign in.
  assert.match(heroComponent, /href="\/login"[\s\S]{0,200}>[\s\S]*?Login[\s\S]*?</);
  // Primary marketing CTA should still send users to pricing.
  assert.match(heroComponent, /href="\/pricing"[\s\S]{0,200}>[\s\S]*?Check our Prices[\s\S]*?</);
  // Secondary CTA should still point to the demo/contact flow.
  assert.match(heroComponent, /href="\/company\/contact"[\s\S]{0,200}>[\s\S]*?Book a Demo[\s\S]*?</);
});

test('DemoSection "Explore interactive demo" CTA points at the demo login flow', () => {
  assert.match(demoSection, /href="\/login\?demo=1"/);
  assert.doesNotMatch(
    demoSection,
    /href="\/company\/contact"[\s\S]{0,200}aria-label="Explore interactive demo"/,
  );
});

test('Dashboard renders a dismissible demo tour banner when ?demo=1 is present', () => {
  assert.match(dashboardClient, /data-testid="demo-tour-banner"/);
  // Demo mode is derived reactively from Next's useSearchParams hook so the
  // banner stays in sync with URL changes (filter/tab navigation).
  assert.match(dashboardClient, /useSearchParams/);
  assert.match(dashboardClient, /searchParams\?\.get\("demo"\) === "1"/);
  // updateFilters preserves the demo flag when rewriting the URL.
  assert.match(dashboardClient, /if \(isDemoMode\) query\.set\("demo", "1"\)/);
  // Deep links into the three demo destinations.
  assert.match(dashboardClient, /\/incidents\/\$\{firstDemoIncidentId\}/);
  assert.match(dashboardClient, /router\.push\("\/exports"\)/);
  assert.match(dashboardClient, /router\.push\("\/demo"\)/);
  // Dismiss control.
  assert.match(dashboardClient, /aria-label="Dismiss demo tour"/);
});

test('.env.example documents the demo credential env vars', () => {
  assert.match(envExample, /NEXT_PUBLIC_DEMO_EMAIL=demo-admin@adc\.local/);
  assert.match(envExample, /NEXT_PUBLIC_DEMO_PASSWORD=DemoAdmin!2345/);
  assert.match(envExample, /LOCAL DEV ONLY/);
});
