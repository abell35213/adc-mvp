/* ── Integrations ──────────────────────────────────────────────── */

import { request } from "./core";
import type { IntegrationConnectionStatus, JsonObject } from "./types";

export interface IntegrationConnectionHealth {
  integration_id: string;
  provider: string;
  domain: string | null;
  status: IntegrationConnectionStatus;
  healthy: boolean;
  reason: string | null;
  last_synced_at_utc: string | null;
  updated_at_utc: string | null;
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
  requested_at_utc: string | null;
  started_at_utc: string | null;
  completed_at_utc: string | null;
  updated_at_utc: string | null;
}

export interface ProviderWebhookEvent {
  webhook_event_id: string;
  provider: string;
  domain: string | null;
  status: string;
  received_at_utc: string;
  correlation_id: string | null;
  processing_latency_ms: number | null;
  retry_count: number | null;
  normalized_error_code: string | null;
}

export function getIntegrationConnections() {
  return request<IntegrationConnectionHealth[]>("/org/integrations");
}

export function getIntegrationOperations(params?: {
  provider?: string;
  status?: string;
  incident_id?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.provider) query.set("provider", params.provider);
  if (params?.status) query.set("status", params.status);
  if (params?.incident_id) query.set("incident_id", params.incident_id);
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<IntegrationOperationDiagnostics[]>(`/integration-operations${suffix}`);
}

export function getWebhookDiagnostics(params?: {
  provider?: string;
  status?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.provider) query.set("provider", params.provider);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<ProviderWebhookEvent[]>(`/admin/ops/webhook-events${suffix}`);
}
