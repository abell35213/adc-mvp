import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');

test('/design-system is development and test only', () => {
  const page = read('app/design-system/page.tsx');
  assert.match(page, /notFound/);
  assert.match(page, /process\.env\.NODE_ENV === "production"/);
});

test('Avatar uses Next Image instead of raw img', () => {
  const misc = read('components/ui/Misc.tsx');
  assert.match(misc, /from "next\/image"/);
  assert.match(misc, /<Image/);
  assert.doesNotMatch(misc, /<img\b/);
});

test('Modal and Drawer include tab loop, shift tab, escape, focus return, and scroll management', () => {
  for (const path of ['components/ui/Modal.tsx', 'components/ui/Drawer.tsx']) {
    const src = read(path);
    assert.match(src, /aria-modal="true"/);
    assert.match(src, /Escape/);
    assert.match(src, /e\.key !== "Tab"/);
    assert.match(src, /e\.shiftKey/);
    assert.match(src, /prev\?\.focus\(\)/);
    assert.match(src, /document\.body\.style\.overflow = "hidden"/);
  }
});
