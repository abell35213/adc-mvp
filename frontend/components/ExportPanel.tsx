/** Export actions panel component.
 *
 * This client component provides controls for generating and managing
 * export packages for a given incident.  It renders a button for
 * generating a court evidence package and lists existing exports
 * along with their status.  Ready exports expose a Download action
 * which invokes the provided onDownload callback.
 */

"use client";

import { type ExportSummary } from "@/lib/api";
import { getExportStatusBadgeClass, getExportStatusLabel } from "@/lib/exportStatus";

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

const CHECKLIST_ITEMS = [
  {
    key: "required_artifacts_present",
    label: "Required artifacts present",
  },
  {
    key: "custody_complete",
    label: "Custody log complete",
  },
  {
    key: "integrity_checks_passed",
    label: "Integrity checks passed",
  },
] as const;

function describeExportIssue(ex: ExportSummary): string {
  if (ex.failure_reason) return ex.failure_reason;
  if (ex.status === "failed") {
    return "Bundle generation failed before completion.";
  }
  return "Export is still processing and not ready to download.";
}

function describeRetryGuidance(ex: ExportSummary): string {
  if (ex.retry_guidance) return ex.retry_guidance;
  if (ex.status === "failed") {
    return "Review missing/invalid source artifacts, then retry generation.";
  }
  return "Wait for processing to finish, then refresh and retry if it stalls.";
}

export default function ExportPanel({
  exports: exportList,
  onExport,
  onDownload,
  exporting = false,
}: ExportPanelProps) {
  const latestExport = exportList[0];
  const readiness = latestExport?.readiness ?? {};
  const checklistSummary = CHECKLIST_ITEMS.map(({ key, label }) => {
    const value = readiness[key];
    return {
      label,
      ready: value === true,
      unknown: value == null,
    };
  });

  const readyCount = checklistSummary.filter((item) => item.ready).length;
  const unknownCount = checklistSummary.filter((item) => item.unknown).length;
  const allReady = readyCount === checklistSummary.length;

  function handlePreExportConfirm() {
    const summaryLines = [
      "This bundle will include:",
      "• Evidence inventory snapshot",
      "• Chain-of-custody timeline",
      "• Integrity verification report",
      "",
      "Readiness checklist:",
      ...checklistSummary.map(
        (item) => `• ${item.ready ? "✅" : item.unknown ? "•" : "⚠️"} ${item.label}`
      ),
      "",
      allReady
        ? "All checks appear ready. Continue generating the export package?"
        : "Some checks are incomplete. Continue generating anyway?",
    ];
    const confirmed = window.confirm(summaryLines.join("\n"));
    if (confirmed) {
      onExport();
    }
  }

  return (
    <div>
      <div className="mb-4 rounded-md border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Export readiness checklist
        </p>
        <ul className="space-y-2 text-sm">
          {checklistSummary.map((item) => (
            <li key={item.label} className="flex items-center gap-2">
              <span
                className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                  item.ready
                    ? "bg-green-100 text-green-700"
                    : item.unknown
                      ? "bg-gray-200 text-gray-600"
                      : "bg-yellow-100 text-yellow-700"
                }`}
              >
                {item.ready ? "✓" : item.unknown ? "?" : "!"}
              </span>
              <span className="text-gray-700 dark:text-gray-200">
                {item.label}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-gray-500">
          {allReady
            ? "Ready to export."
            : unknownCount > 0
              ? "Readiness data is still being collected."
              : "Resolve checklist warnings before generating a final package."}
        </p>
      </div>
      <div className="mb-4">
        <button
          onClick={handlePreExportConfirm}
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
            <li key={ex.export_id} className="rounded border px-4 py-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-gray-600 dark:text-gray-300">
                  {ex.export_id.slice(0, 8)}…
                </span>
                <span className="ml-2 text-xs text-gray-400">
                  {formatTime(ex.created_at_utc)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getExportStatusBadgeClass(ex.status)}`}>
                  {getExportStatusLabel(ex.status)}
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
              {ex.status !== "ready" && (
                <div className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  <p>
                    <span className="font-semibold">Reason:</span>{" "}
                    {describeExportIssue(ex)}
                  </p>
                  <p className="mt-1">
                    <span className="font-semibold">Retry guidance:</span>{" "}
                    {describeRetryGuidance(ex)}
                  </p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
