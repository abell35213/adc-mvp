import type { ExportStatus } from "@/lib/api";

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
  if (status === "ready") return "bg-green-100 text-green-800";
  if (status === "failed" || status === "expired") return "bg-red-100 text-red-800";
  return "bg-yellow-100 text-yellow-800";
}
