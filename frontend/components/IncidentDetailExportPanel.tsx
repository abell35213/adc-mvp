"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createExport,
  downloadExport,
  getExport,
  getExportStatus,
  type ExportProgressStage,
  type ExportStatus,
  type ExportSummary,
  type ExportType,
} from "@/lib/api";
import { getExportStatusBadgeClass, getExportStatusLabel } from "@/lib/exportStatus";
import GenerateExportModal from "@/components/GenerateExportModal";

interface IncidentDetailExportPanelProps {
  incidentId: string;
  exports: ExportSummary[];
  onExportsChanged: () => Promise<void>;
}

const STAGE_TEXT: Record<ExportProgressStage, string> = {
  request_accepted: "Request accepted",
  gathering_incident_data: "Gathering incident data",
  assembling_documents: "Assembling documents",
  packaging_evidence: "Packaging evidence",
  uploading_export: "Uploading export",
  ready_for_download: "Ready for download",
};

function formatBytes(value?: number | null): string {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function IncidentDetailExportPanel({
  incidentId,
  exports,
  onExportsChanged,
}: IncidentDetailExportPanelProps) {
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeExportId, setActiveExportId] = useState<string | null>(null);
  const [status, setStatus] = useState<ExportStatus | null>(null);
  const [stage, setStage] = useState<ExportProgressStage | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [readyExport, setReadyExport] = useState<ExportSummary | null>(null);

  const recentExports = exports.slice(0, 5);
  const recentWarnings = useMemo(
    () =>
      recentExports.reduce((count, item) => {
        const warnings = Array.isArray(item.options_json?.warnings) ? item.options_json.warnings : [];
        return count + warnings.length;
      }, 0),
    [recentExports]
  );

  useEffect(() => {
    if (!activeExportId || !status || (status !== "queued" && status !== "processing" && status !== "requested")) {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const result = await getExportStatus(activeExportId);
        setStatus(result.status);
        setStage(result.progress_stage);
        setErrorMessage(result.error_message ?? "");

        if (result.status === "ready") {
          const full = await getExport(activeExportId);
          setReadyExport(full);
          await onExportsChanged();
          window.clearInterval(timer);
        }

        if (result.status === "failed" || result.status === "expired") {
          await onExportsChanged();
          window.clearInterval(timer);
        }
      } catch (err: unknown) {
        setErrorMessage(err instanceof Error ? err.message : "Unable to poll export status");
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [activeExportId, onExportsChanged, status]);

  async function startExport(payload: {
    exportType: ExportType;
    options: {
      profile: "mvp_default";
      include_media: boolean;
      include_raw_telemetry: boolean;
      include_driver_statement: boolean;
    };
  }) {
    setSubmitting(true);
    setErrorMessage("");
    try {
      const options = payload.exportType === "court_defense" ? payload.options : {};
      const created = await createExport({
        incident_id: incidentId,
        export_type: payload.exportType,
        options_json: options,
      });
      setActiveExportId(created.export_id);
      setStatus(created.status);
      setStage("request_accepted");
      setReadyExport(null);
      setShowModal(false);
      await onExportsChanged();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create export");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownload(exportId: string) {
    const result = await downloadExport(exportId);
    window.open(result.url, "_blank");
  }

  const isProcessing = status === "requested" || status === "queued" || status === "processing";
  const isFailed = status === "failed" || status === "expired";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">Recent exports and generation status.</p>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          New export
        </button>
      </div>

      {isProcessing && (
        <div className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
          <p className="font-medium">ExportProcessingState</p>
          <p>{stage ? STAGE_TEXT[stage] : "Starting export workflow"}</p>
          <p className="text-xs">Polling /exports/{activeExportId}/status…</p>
        </div>
      )}

      {readyExport && (
        <div className="rounded border border-green-200 bg-green-50 p-3 text-sm text-green-900">
          <p className="font-medium">ExportReadyState</p>
          <p>Checksum: {readyExport.package_sha256 ?? "—"}</p>
          <p>Size: {formatBytes(readyExport.byte_size)}</p>
          <button
            onClick={() => handleDownload(readyExport.export_id)}
            className="mt-2 rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
          >
            Download export
          </button>
        </div>
      )}

      {isFailed && (
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
          <p className="font-medium">Export failed</p>
          <p>{errorMessage || "Export did not complete successfully."}</p>
          <button
            className="mt-2 rounded border border-red-300 px-3 py-1 text-xs"
            onClick={() => setShowModal(true)}
          >
            Retry (placeholder)
          </button>
        </div>
      )}

      {errorMessage && !isFailed && <p className="text-sm text-red-600">{errorMessage}</p>}

      {recentExports.length === 0 ? (
        <p className="text-sm text-gray-400">No exports yet.</p>
      ) : (
        <ul className="space-y-2">
          {recentExports.map((item) => (
            <li key={item.export_id} className="rounded border px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-gray-600">{item.export_id.slice(0, 8)}…</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${getExportStatusBadgeClass(item.status)}`}>
                  {getExportStatusLabel(item.status)}
                </span>
              </div>
              <div className="mt-2 flex gap-2">
                {item.status === "ready" && (
                  <button
                    onClick={() => handleDownload(item.export_id)}
                    className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
                  >
                    Download
                  </button>
                )}
                {(item.status === "failed" || item.status === "expired") && (
                  <button
                    onClick={() => setShowModal(true)}
                    className="rounded border border-gray-300 px-3 py-1 text-xs"
                  >
                    Retry placeholder
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <GenerateExportModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={startExport}
        disabled={submitting}
        warningCount={recentWarnings}
      />
    </div>
  );
}
