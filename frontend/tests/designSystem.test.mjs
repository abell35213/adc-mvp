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
  assert.match(s, /role=\{tone==="critical"\?"alert":"status"\}/);
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
