/**
 * TypeScript wrapper for the `.mjs` zod schemas.  The schemas live
 * in `.mjs` (so they can be unit-tested without a TS loader) and are
 * re-exported here with `z.infer<>` so consumers still get full
 * compile-time inference.
 */

import { z } from "zod";
import {
  MeResponseSchema,
  IntegrationValidationLegacyRowSchema,
  IntegrationValidationCurrentRowSchema,
  IntegrationValidationRowSchema,
  IntegrationValidationRowsSchema,
} from "./schemas.mjs";

export {
  MeResponseSchema,
  IntegrationValidationLegacyRowSchema,
  IntegrationValidationCurrentRowSchema,
  IntegrationValidationRowSchema,
  IntegrationValidationRowsSchema,
};

export type MeResponseValidated = z.infer<typeof MeResponseSchema>;
export type IntegrationValidationLegacyRow = z.infer<
  typeof IntegrationValidationLegacyRowSchema
>;
export type IntegrationValidationCurrentRow = z.infer<
  typeof IntegrationValidationCurrentRowSchema
>;
export type IntegrationValidationRow = z.infer<
  typeof IntegrationValidationRowSchema
>;
