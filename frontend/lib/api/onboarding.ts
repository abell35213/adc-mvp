/* ── Onboarding ─────────────────────────────────────────────────── */

import { request } from "./core";
import type {
  OnboardingStepStatus,
  OnboardingReadinessStatus,
  OnboardingImportJobStatus,
  BlockerSeverity,
  InstructionSource,
  JsonObject,
  UtcTimestamp,
} from "./types";

export interface OnboardingReadinessStep {
  key: string;
  label: string;
  status: OnboardingStepStatus;
  order: number;
  completed_at_utc?: UtcTimestamp | null;
  updated_at_utc?: UtcTimestamp | null;
}

export interface OnboardingBlocker {
  code: string;
  title: string;
  detail: string;
  severity: BlockerSeverity;
  blocking_step_key?: string | null;
}

export interface OnboardingImportJob {
  import_job_id: string;
  provider: string;
  status: OnboardingImportJobStatus;
  records_total: number;
  records_succeeded: number;
  records_failed: number;
  completed_at_utc?: UtcTimestamp | null;
}

export interface ExportValidationRun {
  validation_run_id?: string | null;
  status: OnboardingStepStatus;
  validated_at_utc?: UtcTimestamp | null;
  checks: Record<string, boolean>;
}

export interface OnboardingMetricsSnapshot {
  onboarding_started_at_utc?: UtcTimestamp | null;
  latest_activity_at_utc?: UtcTimestamp | null;
  time_to_pilot_ready_hours?: number | null;
  time_to_launch_ready_hours?: number | null;
  import_success_rate: number;
  driver_import_success_rate: number;
  qr_coverage_rate: number;
  valid_driver_phone_ratio: number;
  integration_validation_pass_rate: number;
  sample_incident_completion_rate: number;
  export_validation_rate: number;
  common_blockers: string[];
}

export interface OnboardingAlertCondition {
  code: string;
  title: string;
  severity: BlockerSeverity;
  triggered: boolean;
  detail: string;
}

export interface OrgLaunchReadiness {
  org_id: string;
  status: OnboardingReadinessStatus;
  percent_complete: number;
  steps: OnboardingReadinessStep[];
  blockers: OnboardingBlocker[];
  import_jobs: OnboardingImportJob[];
  latest_export_validation?: ExportValidationRun | null;
  metrics?: OnboardingMetricsSnapshot | null;
  alert_conditions?: OnboardingAlertCondition[];
  reporting_hooks?: JsonObject;
  snapshot_created_at_utc?: UtcTimestamp | null;
}

export interface VehicleQrStats {
  required_vehicle_count: number;
  generated_count: number;
  distributed_count: number;
  confirmed_count: number;
  coverage_blockers: string[];
}

export interface IntegrationValidationResult {
  integration_id: string;
  credentialStatus: OnboardingStepStatus;
  capabilityStatus: OnboardingStepStatus;
  mappingStatus: OnboardingStepStatus;
  messages: string[];
  timestamp: string;
}

export interface ProtocolSetupStepData {
  instruction_set_selected: boolean;
  instruction_source: InstructionSource;
  safety_contact_configured: boolean;
  safety_manager_phone: string | null;
  required_media_prompts_defaulted: boolean;
  export_profile_defaulted: boolean;
  export_profiles_available: string[];
}

export function getOrgOnboardingStatus() {
  return request<OrgLaunchReadiness>("/org/onboarding/status");
}

export function getOrgOnboardingQrStats() {
  return request<VehicleQrStats>("/org/onboarding/qr-stats");
}

/**
 * Raw row shape returned by the *legacy* version of
 * `/org/integrations/validation-results` (pre-redesign).
 */
interface IntegrationValidationResultLegacyResponse {
  integration_key?: string;
  status?: OnboardingStepStatus;
  checked_at_utc?: UtcTimestamp;
  detail?: string;
  errors?: string[];
}

/**
 * Raw row shape returned by the *current* version of
 * `/org/integrations/validation-results`.
 */
interface IntegrationValidationResultCurrentResponse {
  integration_id?: string;
  credentialStatus?: OnboardingStepStatus;
  capabilityStatus?: OnboardingStepStatus;
  mappingStatus?: OnboardingStepStatus;
  messages?: string[];
  timestamp?: string;
}

type IntegrationValidationRawResponse =
  | IntegrationValidationResultLegacyResponse
  | IntegrationValidationResultCurrentResponse;

/**
 * Tagged-union view of a raw validation-result row.  The discriminator
 * is computed from the presence of shape-specific fields rather than a
 * server-supplied flag; once narrowed, downstream code can access each
 * branch's fields directly without `as` casts.
 */
type IntegrationValidationRow =
  | ({ kind: "current" } & IntegrationValidationResultCurrentResponse)
  | ({ kind: "legacy" } & IntegrationValidationResultLegacyResponse);

function tagValidationRow(row: IntegrationValidationRawResponse): IntegrationValidationRow {
  if (
    "credentialStatus" in row ||
    "capabilityStatus" in row ||
    "mappingStatus" in row ||
    "integration_id" in row ||
    "messages" in row ||
    "timestamp" in row
  ) {
    return { kind: "current", ...(row as IntegrationValidationResultCurrentResponse) };
  }
  return { kind: "legacy", ...(row as IntegrationValidationResultLegacyResponse) };
}

function slugify(parts: ReadonlyArray<string>): string {
  return parts
    .join("|")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizeValidationRow(row: IntegrationValidationRow): IntegrationValidationResult {
  if (row.kind === "current") {
    const status = row.credentialStatus ?? "not_started";
    const messages = row.messages ?? [];
    const fallbackId = slugify([row.timestamp ?? "", status, ...messages]);
    return {
      integration_id: row.integration_id ?? `integration-${fallbackId || "unknown"}`,
      credentialStatus: row.credentialStatus ?? status,
      capabilityStatus: row.capabilityStatus ?? status,
      mappingStatus: row.mappingStatus ?? status,
      messages,
      timestamp: row.timestamp ?? new Date(0).toISOString(),
    };
  }
  const status = row.status ?? "not_started";
  const messages = row.errors ?? (row.detail ? [row.detail] : []);
  const fallbackId = slugify([row.checked_at_utc ?? "", status, ...messages]);
  return {
    integration_id: row.integration_key ?? `integration-${fallbackId || "unknown"}`,
    credentialStatus: status,
    capabilityStatus: status,
    mappingStatus: status,
    messages,
    timestamp: row.checked_at_utc ?? new Date(0).toISOString(),
  };
}

export function getIntegrationValidationResults() {
  return request<IntegrationValidationRawResponse[]>(
    "/org/integrations/validation-results"
  ).then((rows) => rows.map(tagValidationRow).map(normalizeValidationRow));
}

export function getProtocolSetupStepData() {
  return request<ProtocolSetupStepData>("/org/onboarding/protocol-setup-step");
}
