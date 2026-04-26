"use client";

import { type ExportSummary } from "@/lib/api";
import ExportListItem from "@/components/exports/ExportListItem";

interface ExportPanelProps {
  exports: ExportSummary[];
  onExport: () => void;
  onDownload: (exportId: string) => void;
  onRetry: (exportId: string) => void;
  exporting?: boolean;
}

export default function ExportPanel({ exports: exportList, onExport, onDownload, onRetry, exporting = false }: ExportPanelProps) {
  const counts = {
    queued: exportList.filter((item) => item.status === "queued" || item.status === "requested").length,
    processing: exportList.filter((item) => item.status === "processing").length,
    ready: exportList.filter((item) => item.status === "ready").length,
    failed: exportList.filter((item) => item.status === "failed" || item.status === "expired").length,
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {Object.entries({ Queued: counts.queued, Processing: counts.processing, Ready: counts.ready, Failed: counts.failed }).map(([k, v]) => (
          <div key={k} className="rounded border border-border-default bg-surface p-3 text-sm">
            <p className="text-xs uppercase text-text-muted">{k}</p>
            <p className="text-xl font-semibold text-text-primary">{v}</p>
          </div>
        ))}
      </div>

      <button onClick={onExport} disabled={exporting} className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
        {exporting ? "Generating…" : "Generate Export"}
      </button>

      {exportList.length === 0 ? (
        <p className="text-sm text-gray-400">No exports yet.</p>
      ) : (
        <div className="space-y-2">
          {exportList.map((ex) => (
            <ExportListItem key={ex.export_id} item={ex} onDownload={onDownload} onRetry={onRetry} />
          ))}
        </div>
      )}
    </div>
  );
}
