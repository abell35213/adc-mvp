"use client";

import Link from "next/link";
import type { ExportSummary } from "@/lib/api";
import { getExportStatusBadgeClass, getExportStatusLabel } from "@/lib/exportStatus";

interface ExportListItemProps {
  item: ExportSummary;
  showIncident?: boolean;
  onDownload?: (exportId: string) => void;
  onRetry?: (exportId: string) => void;
  onDetails?: (exportId: string) => void;
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function warningCount(item: ExportSummary): number {
  const warnings = item.options_json?.warnings;
  return Array.isArray(warnings) ? warnings.length : 0;
}

export default function ExportListItem({ item, showIncident = false, onDownload, onRetry, onDetails }: ExportListItemProps) {
  const shortId = `${item.export_id.slice(0, 10)}…`;
  const warnCount = warningCount(item);

  return (
    <article className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <p className="font-mono text-xs text-text-muted">{shortId}</p>
          <p className="text-xs text-text-secondary">Requested {formatTime(item.created_at_utc ?? item.requested_at_utc)}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getExportStatusBadgeClass(item.status)}`}>
          {getExportStatusLabel(item.status)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-text-secondary sm:grid-cols-3">
        <p>
          <span className="font-medium text-text-primary">Manifest:</span> {item.artifact_count} artifacts · {item.timeline_event_count} events
        </p>
        <p>
          <span className="font-medium text-text-primary">Warnings:</span> {warnCount}
        </p>
        <p className="truncate">
          <span className="font-medium text-text-primary">SHA:</span> {item.package_sha256 ?? "Pending"}
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-surface-muted px-2 py-1 uppercase tracking-wide text-text-secondary">{item.export_type}</span>
        <span className="rounded bg-surface-muted px-2 py-1 uppercase tracking-wide text-text-secondary">{item.profile_id}</span>
        {showIncident && item.incident_id && (
          <Link href={`/incidents/${item.incident_id}`} className="rounded border border-border-default px-2 py-1 text-text-primary hover:bg-surface-muted">
            View incident
          </Link>
        )}
        {onDetails && (
          <button onClick={() => onDetails(item.export_id)} className="rounded border border-border-default px-2 py-1 text-text-secondary hover:bg-surface-muted">
            Details
          </button>
        )}
        {item.status === "ready" && onDownload && (
          <button onClick={() => onDownload(item.export_id)} className="rounded bg-green-600 px-3 py-1 font-medium text-white hover:bg-green-700">
            Download
          </button>
        )}
        {item.status === "failed" && onRetry && (
          <button onClick={() => onRetry(item.export_id)} className="rounded border border-red-300 px-3 py-1 font-medium text-red-700 hover:bg-red-50">
            Retry
          </button>
        )}
      </div>
    </article>
  );
}
