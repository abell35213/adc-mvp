import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('evidence page tracks response pagination state and forwards the active page to the API', () => {
  const source = readFileSync(new URL('../app/evidence/page.tsx', import.meta.url), 'utf8');
  assert.match(source, /const \[page, setPage\] = useState\(1\);/);
  assert.match(source, /const \[pageSize, setPageSize\] = useState\(50\);/);
  assert.match(source, /const \[total, setTotal\] = useState\(0\);/);
  assert.match(source, /listEvidence\(\{\s*page,\s*page_size: pageSize,/);
  assert.match(source, /setPage\(response\.page\);/);
  assert.match(source, /setPageSize\(response\.page_size\);/);
  assert.match(source, /setTotal\(response\.total\);/);
  assert.match(source, /Page \{page\} of \{totalPages\}/);
});

test('evidence page resets to the first page when filters change', () => {
  const source = readFileSync(new URL('../app/evidence/page.tsx', import.meta.url), 'utf8');
  assert.match(source, /setSearch\(e\.target\.value\); setPage\(1\);/);
  assert.match(source, /setStatus\(e\.target\.value\); setPage\(1\);/);
  assert.match(source, /setType\(e\.target\.value\); setPage\(1\);/);
});
