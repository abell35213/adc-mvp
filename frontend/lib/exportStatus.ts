import type { ExportStatus } from "@/lib/api";
import { getExportStateMeta, getStatusBadgeClass } from "@/lib/status";

export const EXPORT_STATUS_LABELS: Record<ExportStatus, string> = {
  requested: getExportStateMeta("requested").label,
  queued: getExportStateMeta("queued").label,
  processing: getExportStateMeta("processing").label,
  ready: getExportStateMeta("ready").label,
  failed: getExportStateMeta("failed").label,
  expired: getExportStateMeta("expired").label,
};

export function getExportStatusLabel(status: ExportStatus): string {
  return EXPORT_STATUS_LABELS[status];
}

export function getExportStatusBadgeClass(status: ExportStatus): string {
  return getStatusBadgeClass(getExportStateMeta(status).tone);
}
