"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createExport,
  downloadExport,
  getExport,
  getExportStatus,
  retryExport,
  type ArtifactSummary,
  type ExportProgressStage,
  type ExportStatus,
  type ExportSummary,
  type ExportType,
  toUserErrorMessage,
} from "@/lib/api";
import { safeOpenDownloadUrl } from "@/lib/safeUrl";
import GenerateExportModal from "@/components/exports/GenerateExportModal";
import { DocumentExportList } from "@/components/exports/DocumentExportList";
import { Alert, Button, Card, CardContent, CardHeader, EmptyState } from "@/components/ui";
import EvidenceStatusPanel, {
  type EvidenceStatusItem,
} from "@/components/integrations/EvidenceStatusPanel";
import type { EvidenceIntegrationStatus } from "@/components/integrations/EvidenceStatusBadge";

interface IncidentDetailExportPanelProps {
  incidentId: string;
  exports: ExportSummary[];
  artifacts: ArtifactSummary[];
  onExportsChanged: () => Promise<void>;
}

const STAGE_TEXT: Record<ExportProgressStage, string> = {
  request_accepted: "Request accepted",
  gathering_incident_data: "Preparing case data",
  assembling_documents: "Rendering packet",
  packaging_evidence: "Packaging evidence",
  uploading_export: "Uploading document",
  ready_for_download: "Ready for download",
};

function formatBytes(value?: number | null): string {
  if (value == null) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function toEvidenceStatus(status: unknown): EvidenceIntegrationStatus {
  const value = String(status ?? "").toLowerCase();
  if (value === "requested" || value === "queued" || value === "in_progress" || value === "available" || value === "partial" || value === "unavailable" || value === "failed") {
    return value;
  }
  return "requested";
}

function formatWindow(start?: string | null, end?: string | null): string | null {
  if (!start && !end) return null;
  const startLabel = start ? new Date(start).toLocaleString() : "—";
  const endLabel = end ? new Date(end).toLocaleString() : "—";
  return `${startLabel} → ${endLabel}`;
}

export default function IncidentDetailExportPanel({
  incidentId,
  exports,
  artifacts,
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
  const latestExport = recentExports[0];
  const latestFailedExportId =
    activeExportId && (status === "failed" || status === "expired")
      ? activeExportId
      : recentExports.find((item) => item.status === "failed")?.export_id ?? null;
  const recentWarnings = useMemo(
    () =>
      recentExports.reduce((count, item) => {
        const warnings = Array.isArray(item.options_json?.warnings) ? item.options_json.warnings : [];
        return count + warnings.length;
      }, 0),
    [recentExports]
  );
  const latestReadinessSnapshot = latestExport?.options_json?.readiness_snapshot as
    | {
        state?: string;
        reasons?: Array<{ message?: string; code?: string }>;
      }
    | undefined;
  const latestReadinessWarning = latestExport?.options_json?.readiness_warning as
    | { message?: string }
    | undefined;

  const integrationStatusItems = useMemo<EvidenceStatusItem[]>(() => {
    const source = latestExport?.options_json?.evidence_statuses;
    if (Array.isArray(source)) {
      return source.map((raw, idx) => {
        const item = (raw ?? {}) as Record<string, unknown>;
        return {
          key: String(item.id ?? `${idx}-${item.evidence_type ?? "evidence"}`),
          evidenceType: String(item.evidence_type ?? item.type ?? "Unknown evidence"),
          status: toEvidenceStatus(item.status),
          requestedWindow: formatWindow(
            typeof item.requested_window_start === "string" ? item.requested_window_start : null,
            typeof item.requested_window_end === "string" ? item.requested_window_end : null
          ),
          operationUrl: typeof item.operation_link === "string" ? item.operation_link : null,
          artifactUrl: typeof item.artifact_link === "string" ? item.artifact_link : null,
          missingReason: typeof item.missing_reason === "string" ? item.missing_reason : null,
          retryAvailable: Boolean(item.retry_available),
        };
      });
    }

    return artifacts.map((artifact) => ({
      key: artifact.artifact_id,
      evidenceType: artifact.artifact_type,
      status:
        artifact.status === "captured"
          ? "available"
          : artifact.status === "unavailable"
            ? "unavailable"
            : "queued",
      requestedWindow: null,
      operationUrl: null,
      artifactUrl: null,
      missingReason: artifact.unavailable_reason,
      retryAvailable: artifact.status === "unavailable",
    }));
  }, [artifacts, latestExport]);

  const preflightPending = integrationStatusItems.filter((item) => item.status === "requested" || item.status === "queued" || item.status === "in_progress");
  const preflightUnavailable = integrationStatusItems.filter((item) => item.status === "unavailable" || item.status === "failed" || item.status === "partial");

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
        setErrorMessage(toUserErrorMessage(err, "Unable to poll export status"));
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [activeExportId, onExportsChanged, status]);

  async function startExport(payload: {
    exportType: ExportType;
    options: {
      profile_id: "court_defense_v1" | "insurer_packet_v1" | "internal_review_v1" | "compliance_audit_v1";
      include_media: boolean;
      include_raw_telemetry: boolean;
      include_driver_statement: boolean;
    };
  }) {
    setSubmitting(true);
    setErrorMessage("");
    try {
      const created = await createExport({
        incident_id: incidentId,
        export_type: payload.exportType,
        options_json: payload.options,
      });
      setActiveExportId(created.export_id);
      setStatus(created.status);
      setStage("request_accepted");
      setReadyExport(null);
      setShowModal(false);
      await onExportsChanged();
    } catch (err: unknown) {
      setErrorMessage(toUserErrorMessage(err, "Failed to create export"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownload(exportId: string) {
    try {
      const result = await downloadExport(exportId);
      const opened = safeOpenDownloadUrl(result.url);
      if (!opened) {
        setErrorMessage(
          "The download link points to an unrecognized host and was blocked. " +
            "Please contact support if this keeps happening.",
        );
      }
    } catch (err: unknown) {
      setErrorMessage(toUserErrorMessage(err, "Failed to download export"));
    }
  }

  async function handleRetry(exportId: string) {
    setSubmitting(true);
    setErrorMessage("");
    try {
      const created = await retryExport(exportId);
      setActiveExportId(created.export_id);
      setStatus(created.status);
      setStage("request_accepted");
      setReadyExport(null);
      await onExportsChanged();
    } catch (err: unknown) {
      setErrorMessage(toUserErrorMessage(err, "Failed to retry export"));
    } finally {
      setSubmitting(false);
    }
  }

  const isProcessing = status === "requested" || status === "queued" || status === "processing";
  const isFailed = status === "failed" || status === "expired";

  return (
    <div className="space-y-4">
      <Card><CardHeader title="Evidence preflight" description="Review evidence availability, missing reasons, and retryability before packet generation."/><CardContent>
        <p className="sr-only">
          Review evidence availability, missing reasons, and retryability before packet generation.
        </p>
        <EvidenceStatusPanel
          items={integrationStatusItems}
          onRetry={(item) => item.retryAvailable && latestFailedExportId && handleRetry(latestFailedExportId)}
          retrying={submitting}
        />
      </CardContent></Card>

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">Recent exports and generation status.</p>
        <Button onClick={() => setShowModal(true)}>Generate Document</Button>
      </div>

      {latestReadinessSnapshot && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">
            Readiness at request time: {(latestReadinessSnapshot.state ?? "unknown").replaceAll("_", " ")}
          </p>
          {latestReadinessWarning?.message && <p className="text-xs">{latestReadinessWarning.message}</p>}
          {Array.isArray(latestReadinessSnapshot.reasons) && latestReadinessSnapshot.reasons.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-xs">
              {latestReadinessSnapshot.reasons.slice(0, 3).map((reason, index) => (
                <li key={`${reason.code ?? "reason"}-${index}`}>{reason.message ?? reason.code ?? "Readiness reason unavailable"}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {isProcessing && (
        <Alert tone="informational" title="Document generation is in progress" description={stage ? STAGE_TEXT[stage] : "Starting document workflow"} />
      )}

      {readyExport && (
        <Alert tone="success" title="Defense document is ready" description={`Size: ${formatBytes(readyExport.byte_size)}`} action={<Button size="sm" onClick={() => handleDownload(readyExport.export_id)}>Download document</Button>} />
      )}

      {isFailed && (
        <Alert tone="critical" title="Document could not be generated" description={errorMessage || "Document rendering failed. Retry generation or contact support if the problem continues."} action={<Button size="sm" variant="secondary" onClick={() => latestFailedExportId && handleRetry(latestFailedExportId)} disabled={!latestFailedExportId || submitting}>Retry generation</Button>} />
      )}

      {errorMessage && !isFailed && <Alert tone="critical" title="Document workflow needs attention" description={errorMessage} />}

      {recentExports.length === 0 ? (
        <EmptyState title="No documents for this case" message="Generate the first defense-ready case document when required evidence is available."/>
      ) : (
        <DocumentExportList items={recentExports} showIncident={false} onDownload={handleDownload} onRetry={handleRetry} onDetails={() => undefined} />
      )}

      <GenerateExportModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={startExport}
        disabled={submitting}
        warningCount={recentWarnings}
        preflightPendingCount={preflightPending.length}
        preflightUnavailableCount={preflightUnavailable.length}
        preflightWarnings={preflightUnavailable.map((item) => `${item.evidenceType}: ${item.missingReason ?? item.status}`)}
      />
    </div>
  );
}
