import test from 'node:test';
import assert from 'node:assert/strict';
import {
  MeResponseSchema,
  IntegrationValidationLegacyRowSchema,
  IntegrationValidationCurrentRowSchema,
  IntegrationValidationRowSchema,
  IntegrationValidationRowsSchema,
} from '../lib/api/schemas.mjs';

/* ── MeResponseSchema ───────────────────────────────────────────── */

test('MeResponseSchema accepts a well-formed payload', () => {
  const parsed = MeResponseSchema.parse({
    user_id: 'u-1',
    email: 'a@b.com',
    role: 'safety_manager',
    org_ids: ['org-1', 'org-2'],
  });
  assert.equal(parsed.user_id, 'u-1');
  assert.deepEqual(parsed.org_ids, ['org-1', 'org-2']);
});

test('MeResponseSchema rejects missing fields', () => {
  const result = MeResponseSchema.safeParse({ user_id: 'u-1', email: 'a@b.com', role: 'x' });
  assert.equal(result.success, false);
});

test('MeResponseSchema rejects wrong field types', () => {
  const result = MeResponseSchema.safeParse({
    user_id: 'u-1',
    email: 'a@b.com',
    role: 'x',
    org_ids: 'not-an-array',
  });
  assert.equal(result.success, false);
});

/* ── IntegrationValidation row schemas ──────────────────────────── */

test('IntegrationValidationCurrentRowSchema accepts a current-shape row', () => {
  const parsed = IntegrationValidationCurrentRowSchema.parse({
    integration_id: 'samsara',
    credentialStatus: 'completed',
    capabilityStatus: 'in_progress',
    mappingStatus: 'not_started',
    messages: ['ok'],
    timestamp: '2026-04-26T00:00:00Z',
  });
  assert.equal(parsed.integration_id, 'samsara');
  assert.equal(parsed.credentialStatus, 'completed');
});

test('IntegrationValidationLegacyRowSchema accepts a legacy-shape row', () => {
  const parsed = IntegrationValidationLegacyRowSchema.parse({
    integration_key: 'samsara',
    status: 'blocked',
    checked_at_utc: '2026-04-26T00:00:00Z',
    detail: 'rate limited',
    errors: ['429'],
  });
  assert.equal(parsed.integration_key, 'samsara');
  assert.equal(parsed.status, 'blocked');
});

test('IntegrationValidationRowSchema accepts both branches', () => {
  assert.equal(
    IntegrationValidationRowSchema.safeParse({ integration_id: 'x', credentialStatus: 'completed' }).success,
    true,
  );
  assert.equal(
    IntegrationValidationRowSchema.safeParse({ integration_key: 'x', status: 'completed' }).success,
    true,
  );
});

test('IntegrationValidationCurrentRowSchema rejects an invalid status enum', () => {
  // Union schema is intentionally permissive (both branches all-optional, so
  // unknown extra fields are stripped when matching the legacy branch).
  // The branch schemas themselves still validate enum values strictly.
  const result = IntegrationValidationCurrentRowSchema.safeParse({
    credentialStatus: 'not-a-real-status',
  });
  assert.equal(result.success, false);
});

test('IntegrationValidationRowsSchema accepts an array of mixed-shape rows', () => {
  const parsed = IntegrationValidationRowsSchema.parse([
    { integration_id: 'a', credentialStatus: 'completed' },
    { integration_key: 'b', status: 'blocked' },
    {},
  ]);
  assert.equal(parsed.length, 3);
});

test('IntegrationValidationRowsSchema rejects a non-array', () => {
  const result = IntegrationValidationRowsSchema.safeParse({});
  assert.equal(result.success, false);
});
