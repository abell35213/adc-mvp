/* ── Integrations ──────────────────────────────────────────────── */

import { request, buildQuery } from "./core";
import type { IntegrationConnectionStatus, JsonObject, UtcTimestamp } from "./types";

export interface IntegrationConnectionHealth {
  integration_id: string;
  provider: string;
  domain: string | null;
  status: IntegrationConnectionStatus;
  healthy: boolean;
  reason: string | null;
  last_synced_at_utc: UtcTimestamp | null;
  updated_at_utc: UtcTimestamp | null;
}

export interface IntegrationOperationDiagnostics {
  operation_id: string;
  org_id: string | null;
  incident_id: string | null;
  connection_id: string | null;
  provider: string;
  domain: string | null;
  operation_type: string;
  status: string;
  correlation_id: string | null;
  external_reference: string | null;
  external_reference_id: string | null;
  payload_json: JsonObject;
  result_json: JsonObject;
  error_message: string | null;
  error_code: string | null;
  error_category: string | null;
  error_provider_key: string | null;
  error_retryable: boolean | null;
  error_user_facing_message: string | null;
  error_operator_message: string | null;
  requested_at_utc: UtcTimestamp | null;
  started_at_utc: UtcTimestamp | null;
  completed_at_utc: UtcTimestamp | null;
  updated_at_utc: UtcTimestamp | null;
}

export interface ProviderWebhookEvent {
  webhook_event_id: string;
  provider: string;
  domain: string | null;
  status: string;
  received_at_utc: UtcTimestamp;
  correlation_id: string | null;
  processing_latency_ms: number | null;
  retry_count: number | null;
  normalized_error_code: string | null;
}

export function getIntegrationConnections() {
  return request<IntegrationConnectionHealth[]>("/org/integrations");
}

export interface GetIntegrationOperationsParams {
  provider?: string;
  status?: string;
  incident_id?: string;
  limit?: number;
}

export function getIntegrationOperations(params?: GetIntegrationOperationsParams) {
  return request<IntegrationOperationDiagnostics[]>(
    `/integration-operations${buildQuery(params)}`
  );
}

export interface GetWebhookDiagnosticsParams {
  provider?: string;
  status?: string;
  limit?: number;
}

export function getWebhookDiagnostics(params?: GetWebhookDiagnosticsParams) {
  return request<ProviderWebhookEvent[]>(
    `/admin/ops/webhook-events${buildQuery(params)}`
  );
}
