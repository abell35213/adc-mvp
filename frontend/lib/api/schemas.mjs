/**
 * Runtime validation schemas for API responses.
 *
 * Schemas live in `.mjs` so they can be unit-tested by the existing
 * `node --test` runner without any TypeScript loader.  The matching
 * `schemas.ts` re-exports them with `z.infer<>` types so consumers
 * still benefit from compile-time inference.
 *
 * Usage pattern:
 *
 *   import { MeResponseSchema } from "./schemas";
 *   const me = MeResponseSchema.parse(rawJson);
 *
 * or, via the `requestValidated` helper in core.ts, the schema is
 * applied to the parsed response automatically.
 */

import { z } from "zod";

/* ── Auth ──────────────────────────────────────────────────────── */

export const MeResponseSchema = z.object({
  user_id: z.string(),
  email: z.string(),
  role: z.string(),
  org_ids: z.array(z.string()),
});

/* ── Onboarding: integration validation results ───────────────── */
/*
 * Mirrors the legacy/current discriminated union introduced in
 * Block 7.  The discriminator is the *presence* of shape-specific
 * fields rather than a server-supplied flag, so we use a plain
 * union and let the consumer (or `tagValidationRow`) pick the
 * branch.  Both branches keep every field optional because the
 * upstream API does so.
 */

const OnboardingStepStatusSchema = z.enum([
  "not_started",
  "in_progress",
  "completed",
  "blocked",
]);

export const IntegrationValidationLegacyRowSchema = z.object({
  integration_key: z.string().optional(),
  status: OnboardingStepStatusSchema.optional(),
  checked_at_utc: z.string().optional(),
  detail: z.string().optional(),
  errors: z.array(z.string()).optional(),
});

export const IntegrationValidationCurrentRowSchema = z.object({
  integration_id: z.string().optional(),
  credentialStatus: OnboardingStepStatusSchema.optional(),
  capabilityStatus: OnboardingStepStatusSchema.optional(),
  mappingStatus: OnboardingStepStatusSchema.optional(),
  messages: z.array(z.string()).optional(),
  timestamp: z.string().optional(),
});

export const IntegrationValidationRowSchema = z.union([
  IntegrationValidationCurrentRowSchema,
  IntegrationValidationLegacyRowSchema,
]);

export const IntegrationValidationRowsSchema = z.array(
  IntegrationValidationRowSchema
);
