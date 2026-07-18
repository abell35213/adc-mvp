import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');

test('Button variants and loading/disabled behavior exist', () => {
  const s = read('components/ui/Button.tsx');
  for (const v of ['primary', 'secondary', 'quiet', 'destructive']) {
    assert.match(s, new RegExp(v));
  }
  assert.match(s, /aria-busy/);
  assert.match(s, /disabled=\{isDisabled\|\|loading\}/);
});

test('IconButton requires accessible names', () => {
  const s = read('components/ui/IconButton.tsx');
  assert.match(s, /label:string/);
  assert.match(s, /aria-label=\{label\}/);
});

test('StatusBadge renders readable labels with restrained tones', () => {
  const s = read('components/ui/StatusBadge.tsx');
  assert.match(s, /children:ReactNode/);
  assert.match(read('lib/design/tokens.ts'), /neutral.*informational.*success.*warning.*critical/s);
});

test('Tabs expose keyboard and ARIA behavior', () => {
  const s = read('components/ui/Tabs.tsx');
  assert.match(s, /role="tablist"/);
  assert.match(s, /ArrowRight/);
  assert.match(s, /aria-selected/);
});

test('FormField associates labels, help, and errors', () => {
  const s = read('components/ui/FormField.tsx');
  assert.match(s, /htmlFor=\{controlId\}/);
  assert.match(s, /role="alert"/);
  assert.match(s, /aria-invalid/);
});

test('EmptyState supports actions', () => {
  const s = read('components/ui/EmptyState.tsx');
  assert.match(s, /primaryAction/);
  assert.match(s, /secondaryAction/);
});

test('Alert semantics distinguish critical announcements', () => {
  const s = read('components/ui/Alert.tsx');
  assert.match(s, /role=\{tone === "critical" \? "alert" : "status"\}/);
});

test('Modal and Drawer close with escape and restore focus', () => {
  for (const p of ['components/ui/Modal.tsx', 'components/ui/Drawer.tsx']) {
    const s = read(p);
    assert.match(s, /aria-modal="true"/);
    assert.match(s, /Escape/);
    assert.match(s, /prev\?\.focus/);
  }
});

test('Dropdown exposes menu roles and disabled/destructive items', () => {
  const s = read('components/ui/Misc.tsx');
  assert.match(s, /role="menu"/);
  assert.match(s, /role="menuitem"/);
  assert.match(s, /destructive/);
});

test('ProgressBar exposes numeric semantics', () => {
  const s = read('components/ui/ProgressBar.tsx');
  assert.match(s, /role="progressbar"/);
  assert.match(s, /aria-valuenow/);
  assert.match(s, /aria-valuemin=\{0\}/);
});


function luminance(hex) {
  const parts = hex.match(/[0-9a-f]{2}/gi).map((part) => parseInt(part, 16) / 255);
  const [r, g, b] = parts.map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground, background) {
  const a = luminance(foreground);
  const b = luminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

test('semantic color tokens meet normal-text contrast targets', () => {
  const css = read('app/globals.css');
  const token = (name) => css.match(new RegExp(`${name}: (#(?:[0-9a-fA-F]{6}))`))[1];
  assert.ok(contrast(token('--text-inverse'), token('--action-primary')) >= 4.5);
  assert.ok(contrast(token('--text-muted'), token('--page')) >= 4.5);
});

test('Alert title is not a fixed h3 by default', () => {
  const s = read('components/ui/Alert.tsx');
  assert.match(s, /titleAs: TitleElement = "div"/);
  assert.doesNotMatch(s, /<h3 className="text-sm font-semibold text-text-primary">\{title\}<\/h3>/);
});
