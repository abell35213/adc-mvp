import type { ExportStatus } from "@/lib/api";
import { statusBadgeClass } from "@/lib/design/tokens";

export const EXPORT_STATUS_LABELS: Record<ExportStatus, string> = {
  requested: "Requested",
  queued: "Queued",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  expired: "Expired",
};

export function getExportStatusLabel(status: ExportStatus): string {
  return EXPORT_STATUS_LABELS[status];
}

export function getExportStatusBadgeClass(status: ExportStatus): string {
  if (status === "ready") return statusBadgeClass("success");
  if (status === "failed" || status === "expired") return statusBadgeClass("critical");
  return statusBadgeClass("warning");
}
