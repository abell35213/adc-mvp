/** Export actions panel component. */

"use client";

import { type ExportSummary } from "@/lib/api";

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface ExportPanelProps {
  exports: ExportSummary[];
  onExport: () => void;
  onDownload: (exportId: string) => void;
  exporting?: boolean;
}

export default function ExportPanel({
  exports: exportList,
  onExport,
  onDownload,
  exporting = false,
}: ExportPanelProps) {
  return (
    <div>
      <div className="mb-4">
        <button
          onClick={onExport}
          disabled={exporting}
          className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {exporting ? "Generating…" : "Generate Court Package"}
        </button>
      </div>
      {exportList.length === 0 ? (
        <p className="text-sm text-gray-400">No exports yet.</p>
      ) : (
        <ul className="space-y-2">
          {exportList.map((ex) => (
            <li
              key={ex.export_id}
              className="flex items-center justify-between rounded border px-4 py-3 text-sm"
            >
              <div>
                <span className="font-mono text-xs text-gray-600 dark:text-gray-300">
                  {ex.export_id.slice(0, 8)}…
                </span>
                <span className="ml-2 text-xs text-gray-400">{formatTime(ex.created_at_utc)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    ex.status === "ready"
                      ? "bg-green-100 text-green-800"
                      : ex.status === "failed"
                        ? "bg-red-100 text-red-800"
                        : "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {ex.status}
                </span>
                {ex.status === "ready" && (
                  <button
                    onClick={() => onDownload(ex.export_id)}
                    className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
                  >
                    Download ZIP
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
