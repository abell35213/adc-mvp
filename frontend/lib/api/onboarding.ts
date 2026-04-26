/* ── Onboarding ─────────────────────────────────────────────────── */

import { request } from "./core";
import type {
  OnboardingStepStatus,
  OnboardingReadinessStatus,
  OnboardingImportJobStatus,
  BlockerSeverity,
  InstructionSource,
  JsonObject,
} from "./types";

export interface OnboardingReadinessStep {
  key: string;
  label: string;
  status: OnboardingStepStatus;
  order: number;
  completed_at_utc?: string | null;
  updated_at_utc?: string | null;
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
  completed_at_utc?: string | null;
}

export interface ExportValidationRun {
  validation_run_id?: string | null;
  status: OnboardingStepStatus;
  validated_at_utc?: string | null;
  checks: Record<string, boolean>;
}

export interface OnboardingMetricsSnapshot {
  onboarding_started_at_utc?: string | null;
  latest_activity_at_utc?: string | null;
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
  snapshot_created_at_utc?: string | null;
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

type IntegrationValidationResultLegacyResponse = {
  integration_key?: string;
  status?: OnboardingStepStatus;
  checked_at_utc?: string;
  detail?: string;
  errors?: string[];
};

type IntegrationValidationResultCurrentResponse = {
  integration_id?: string;
  credentialStatus?: OnboardingStepStatus;
  capabilityStatus?: OnboardingStepStatus;
  mappingStatus?: OnboardingStepStatus;
  messages?: string[];
  timestamp?: string;
};

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

export function getIntegrationValidationResults() {
  return request<Array<IntegrationValidationResultLegacyResponse | IntegrationValidationResultCurrentResponse>>(
    "/org/integrations/validation-results"
  ).then((rows) =>
    rows.map((row) => {
      const status = (row as IntegrationValidationResultCurrentResponse).credentialStatus
        ?? (row as IntegrationValidationResultLegacyResponse).status
        ?? "not_started";
      const mappedMessages = (row as IntegrationValidationResultCurrentResponse).messages
        ?? (row as IntegrationValidationResultLegacyResponse).errors
        ?? ((row as IntegrationValidationResultLegacyResponse).detail
          ? [(row as IntegrationValidationResultLegacyResponse).detail as string]
          : []);
      const fallbackIdSource = [
        (row as IntegrationValidationResultCurrentResponse).timestamp
          ?? (row as IntegrationValidationResultLegacyResponse).checked_at_utc
          ?? "",
        status,
        ...mappedMessages,
      ]
        .join("|")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      return {
        integration_id:
          (row as IntegrationValidationResultCurrentResponse).integration_id
          ?? (row as IntegrationValidationResultLegacyResponse).integration_key
          ?? `integration-${fallbackIdSource || "unknown"}`,
        credentialStatus: (row as IntegrationValidationResultCurrentResponse).credentialStatus ?? status,
        capabilityStatus: (row as IntegrationValidationResultCurrentResponse).capabilityStatus ?? status,
        mappingStatus: (row as IntegrationValidationResultCurrentResponse).mappingStatus ?? status,
        messages: mappedMessages,
        timestamp:
          (row as IntegrationValidationResultCurrentResponse).timestamp
          ?? (row as IntegrationValidationResultLegacyResponse).checked_at_utc
          ?? new Date(0).toISOString(),
      };
    })
  );
}

export function getProtocolSetupStepData() {
  return request<ProtocolSetupStepData>("/org/onboarding/protocol-setup-step");
}
