import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildQuery, parseApiErrorPayload } from '../lib/api/queryString.mjs';

/* ── buildQuery ─────────────────────────────────────────────────── */

test('buildQuery returns empty string for missing or empty params', () => {
  assert.equal(buildQuery(), '');
  assert.equal(buildQuery(undefined), '');
  assert.equal(buildQuery({}), '');
});

test('buildQuery skips undefined, null, and empty-string values', () => {
  assert.equal(
    buildQuery({ a: undefined, b: null, c: '', d: 0, e: false }),
    '?d=0&e=false',
  );
});

test('buildQuery encodes values via URLSearchParams', () => {
  assert.equal(
    buildQuery({ q: 'hello world', tag: 'a/b' }),
    '?q=hello+world&tag=a%2Fb',
  );
});

test('buildQuery stringifies numbers and booleans', () => {
  assert.equal(buildQuery({ page: 2, page_size: 25, active: true }), '?page=2&page_size=25&active=true');
});

/* ── parseApiErrorPayload ───────────────────────────────────────── */

test('parseApiErrorPayload returns empty object for non-object inputs', () => {
  assert.deepEqual(parseApiErrorPayload(null), {});
  assert.deepEqual(parseApiErrorPayload(undefined), {});
  assert.deepEqual(parseApiErrorPayload('boom'), {});
  assert.deepEqual(parseApiErrorPayload(42), {});
  assert.deepEqual(parseApiErrorPayload([{ detail: 'x' }]), {});
});

test('parseApiErrorPayload extracts string detail as message', () => {
  assert.deepEqual(parseApiErrorPayload({ detail: 'Bad request' }), {
    message: 'Bad request',
  });
});

test('parseApiErrorPayload extracts structured detail fields', () => {
  assert.deepEqual(
    parseApiErrorPayload({
      detail: {
        message: 'Export expired',
        code: 'EXPORT_EXPIRED',
        retry_hint: 'Generate a new export.',
        correlation_id: 'abc-123',
      },
    }),
    {
      message: 'Export expired',
      code: 'EXPORT_EXPIRED',
      retryHint: 'Generate a new export.',
      correlationId: 'abc-123',
    },
  );
});

test('parseApiErrorPayload drops non-string fields from structured detail', () => {
  assert.deepEqual(
    parseApiErrorPayload({
      detail: { message: 'x', code: 42, retry_hint: null, correlation_id: { not: 'a string' } },
    }),
    { message: 'x', code: undefined, retryHint: undefined, correlationId: undefined },
  );
});

test('parseApiErrorPayload returns empty object when detail is missing or wrong shape', () => {
  assert.deepEqual(parseApiErrorPayload({}), {});
  assert.deepEqual(parseApiErrorPayload({ detail: 123 }), {});
  assert.deepEqual(parseApiErrorPayload({ detail: ['a'] }), {});
});


/* ── request header defaults ───────────────────────────────────── */

test('request helper only adds JSON Content-Type when a body is present', () => {
  const core = readFileSync(new URL('../lib/api/core.ts', import.meta.url), 'utf8');
  assert.match(core, /export function mergeHeaders\(init: HeadersInit \| undefined, body\?: BodyInit \| null\)/);
  assert.match(core, /body !== undefined && body !== null && !headers\.has\("Content-Type"\)/);
  assert.match(core, /credentials: init\?\.credentials \?\? "include"/);
});

test('GET and HEAD without bodies do not automatically receive Content-Type', () => {
  const core = readFileSync(new URL('../lib/api/core.ts', import.meta.url), 'utf8');
  assert.doesNotMatch(core, /headers\.set\("Content-Type", "application\/json"\);[\s\S]*return headers;[\s\S]*const headers = mergeHeaders\(init\?\.headers\);/);
  assert.match(core, /const headers = mergeHeaders\(init\?\.headers, init\?\.body\);/);
});
