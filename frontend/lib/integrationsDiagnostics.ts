import type { IntegrationOperationDiagnostics } from "@/lib/api";

export function normalizeErrorCode(operation: IntegrationOperationDiagnostics): string {
  if (operation.error_category) return operation.error_category.toUpperCase();
  if (operation.error_code) return operation.error_code.toUpperCase();
  if ((operation.error_message ?? "").toLowerCase().includes("timeout")) return "TIMEOUT";
  return "NONE";
}

export function parseRetryCount(operation: IntegrationOperationDiagnostics): number {
  const retryFromResult = operation.result_json["retry_count"];
  const retryFromPayload = operation.payload_json["retry_count"];
  const retryCount = Number(
    (typeof retryFromResult === "number" ? retryFromResult : undefined) ??
      (typeof retryFromPayload === "number" ? retryFromPayload : undefined) ??
      0
  );
  return Number.isNaN(retryCount) ? 0 : retryCount;
}
