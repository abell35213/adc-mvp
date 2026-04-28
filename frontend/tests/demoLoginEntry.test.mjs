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
  // Prefill is gated by the demo flag — bail out early when not in demo mode.
  assert.match(loginPage, /if \(!isDemoMode\) return;/);
  // Sources the demo credentials from public env vars (with fallbacks).
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

test('Hero component exposes a "Try the demo" CTA pointing at /login?demo=1', () => {
  assert.match(heroComponent, /href="\/login\?demo=1"/);
  assert.match(heroComponent, /Try the demo/);
  assert.match(heroComponent, /data-testid="hero-try-demo"/);
  // The standalone "Login" link is still present so existing users can sign in.
  assert.match(heroComponent, /href="\/login"\s+className/);
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
  assert.match(dashboardClient, /params\.get\("demo"\) === "1"/);
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
