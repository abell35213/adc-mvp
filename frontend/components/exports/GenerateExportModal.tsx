"use client";

import { useMemo, useState } from "react";
import type { ExportType } from "@/lib/api";

interface ExportOptions {
  profile_id: "court_defense_v1" | "insurer_packet_v1" | "internal_review_v1" | "compliance_audit_v1";
  include_media: boolean;
  include_raw_telemetry: boolean;
  include_driver_statement: boolean;
}

interface GenerateExportModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { exportType: ExportType; options: ExportOptions }) => Promise<void>;
  disabled?: boolean;
  warningCount?: number;
  preflightPendingCount?: number;
  preflightUnavailableCount?: number;
  preflightWarnings?: string[];
}

const EXPORT_TYPE_OPTIONS: Array<{ value: ExportType; label: string; description: string }> = [
  {
    value: "court_defense",
    label: "Court Defense (MVP)",
    description: "Includes evidence package sections required by the MVP profile.",
  },
  {
    value: "insurer_packet",
    label: "Insurer Packet",
    description: "Placeholder for insurer-specific packet workflow.",
  },
  {
    value: "internal_review",
    label: "Internal Review",
    description: "Placeholder for internal review workflow.",
  },
  {
    value: "compliance_audit",
    label: "Compliance Audit",
    description: "Placeholder for compliance audit workflow.",
  },
];

const NON_BLOCKING_WARNINGS = [
  "Unavailable artifacts are flagged in the package and do not block export generation.",
  "Timeline ordering is best-effort if upstream systems report delayed timestamps.",
];

const DEFAULT_OPTIONS: ExportOptions = {
  profile_id: "court_defense_v1",
  include_media: true,
  include_raw_telemetry: true,
  include_driver_statement: true,
};

export default function GenerateExportModal({
  open,
  onClose,
  onSubmit,
  disabled = false,
  warningCount = 0,
  preflightPendingCount = 0,
  preflightUnavailableCount = 0,
  preflightWarnings = [],
}: GenerateExportModalProps) {
  const [step, setStep] = useState<"configure" | "review">("configure");
  const [exportType, setExportType] = useState<ExportType>("court_defense");
  const [options, setOptions] = useState<ExportOptions>(DEFAULT_OPTIONS);

  const includedSections = useMemo(
    () => [
      options.include_media ? "Incident media bundle" : null,
      options.include_raw_telemetry ? "Raw telemetry records" : null,
      options.include_driver_statement ? "Driver statement + protocol timeline" : null,
      "Evidence inventory snapshot",
      "Chain-of-custody digest",
      "Integrity verification report",
    ].filter(Boolean) as string[],
    [options]
  );

  if (!open) return null;

  const isMvpExport = exportType === "court_defense";
  const isInsurerExport = exportType === "insurer_packet";

  async function handleSubmit() {
    const profileId =
      exportType === "court_defense"
        ? "court_defense_v1"
        : exportType === "insurer_packet"
          ? "insurer_packet_v1"
          : exportType === "internal_review"
            ? "internal_review_v1"
            : "compliance_audit_v1";
    await onSubmit({ exportType, options: { ...options, profile_id: profileId } });
    setStep("configure");
  }

  function handleClose() {
    setStep("configure");
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Generate export</h3>
            <p className="text-sm text-gray-500">
              {step === "configure" ? "Choose export settings." : "Review included sections and preflight warnings."}
            </p>
          </div>
          <button onClick={handleClose} className="text-sm text-gray-500 hover:underline">
            Close
          </button>
        </div>

        {step === "configure" ? (
          <div className="space-y-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">
              Export type
              <select
                value={exportType}
                onChange={(e) => setExportType(e.target.value as ExportType)}
                className="mt-1 w-full rounded border border-gray-300 p-2 text-sm dark:border-gray-600 dark:bg-gray-900"
              >
                {EXPORT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="text-xs text-gray-500">
              {EXPORT_TYPE_OPTIONS.find((option) => option.value === exportType)?.description}
            </p>

            {isMvpExport || isInsurerExport ? (
              <div className="rounded border border-blue-100 bg-blue-50 p-3 text-sm">
                <p className="font-medium text-blue-900">
                  {isMvpExport ? "Court defense profile defaults" : "Insurer packet profile defaults"}
                </p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={options.include_media}
                      onChange={(e) => setOptions((prev) => ({ ...prev, include_media: e.target.checked }))}
                    />
                    Include media
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={options.include_raw_telemetry}
                      onChange={(e) =>
                        setOptions((prev) => ({ ...prev, include_raw_telemetry: e.target.checked }))
                      }
                    />
                    Include raw telemetry
                  </label>
                  <label className="flex items-center gap-2 sm:col-span-2">
                    <input
                      type="checkbox"
                      checked={options.include_driver_statement}
                      onChange={(e) =>
                        setOptions((prev) => ({ ...prev, include_driver_statement: e.target.checked }))
                      }
                    />
                    Include driver statement
                  </label>
                </div>
              </div>
            ) : (
              <div className="rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                Non-court export types are placeholders and currently submit with no custom options.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Included sections</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600 dark:text-gray-300">
                {includedSections.map((section) => (
                  <li key={section}>{section}</li>
                ))}
              </ul>
            </div>
            <div className="rounded border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-900">Preflight visibility</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-900">
                <li>{preflightPendingCount} evidence item(s) are still pending upstream retrieval.</li>
                <li>{preflightUnavailableCount} evidence item(s) are unavailable/partial and will be flagged in packet rationale.</li>
                {NON_BLOCKING_WARNINGS.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
                {warningCount > 0 && <li>{warningCount} warning(s) detected on recent export attempts.</li>}
                {preflightWarnings.slice(0, 5).map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <div className="mt-6 flex justify-between">
          <button
            onClick={() => setStep((prev) => (prev === "configure" ? "review" : "configure"))}
            className="rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
          >
            {step === "configure" ? "Review" : "Back"}
          </button>
          {step === "review" && (
            <button
              onClick={handleSubmit}
              disabled={disabled}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {disabled ? "Submitting…" : "Submit export"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
