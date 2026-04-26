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

const DEFAULT_OPTIONS: ExportOptions = {
  profile_id: "court_defense_v1",
  include_media: true,
  include_raw_telemetry: true,
  include_driver_statement: true,
};

const EXPORT_TYPES: Array<{ value: ExportType; label: string; profileId: ExportOptions["profile_id"] }> = [
  { value: "court_defense", label: "Court defense", profileId: "court_defense_v1" },
  { value: "insurer_packet", label: "Insurer packet", profileId: "insurer_packet_v1" },
  { value: "internal_review", label: "Internal review", profileId: "internal_review_v1" },
  { value: "compliance_audit", label: "Compliance audit", profileId: "compliance_audit_v1" },
];

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
  const [exportType, setExportType] = useState<ExportType>("court_defense");
  const [options, setOptions] = useState<ExportOptions>(DEFAULT_OPTIONS);

  const includedSections = useMemo(() => {
    const sections = [
      "Evidence inventory snapshot",
      "Chain-of-custody timeline",
      "Integrity verification report",
    ];
    if (options.include_media) sections.push("Incident media bundle");
    if (options.include_raw_telemetry) sections.push("Raw telemetry records");
    if (options.include_driver_statement) sections.push("Driver statement and protocol logs");
    return sections;
  }, [options]);

  if (!open) return null;

  async function handleGenerate() {
    const profileId = EXPORT_TYPES.find((item) => item.value === exportType)?.profileId ?? "court_defense_v1";
    await onSubmit({ exportType, options: { ...options, profile_id: profileId } });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-3xl rounded-lg border border-border-default bg-surface p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-text-primary">Generate Export</h3>
            <p className="text-sm text-text-secondary">Choose packet type, review sections, and confirm warnings before generation.</p>
          </div>
          <button onClick={onClose} className="rounded border border-border-default px-3 py-1 text-sm text-text-secondary hover:bg-surface-muted">Cancel</button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-4">
            <label className="block text-sm font-medium text-text-primary">
              Packet type
              <select
                value={exportType}
                onChange={(e) => setExportType(e.target.value as ExportType)}
                className="mt-1 w-full rounded-md border border-border-default bg-surface px-3 py-2 text-sm"
              >
                {EXPORT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </label>

            <div className="rounded-md border border-border-default bg-surface-muted p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Included sections</p>
              <div className="mt-2 space-y-2 text-sm">
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_media} onChange={(e) => setOptions((prev) => ({ ...prev, include_media: e.target.checked }))} />Include media</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_raw_telemetry} onChange={(e) => setOptions((prev) => ({ ...prev, include_raw_telemetry: e.target.checked }))} />Include telemetry</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_driver_statement} onChange={(e) => setOptions((prev) => ({ ...prev, include_driver_statement: e.target.checked }))} />Include driver statement</label>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-md border border-border-default p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Manifest preview</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-secondary">
                {includedSections.map((section) => <li key={section}>{section}</li>)}
              </ul>
            </div>
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">Warnings panel</p>
              <p className="text-xs">Pending: {preflightPendingCount} · Unavailable: {preflightUnavailableCount} · Recent warnings: {warningCount}</p>
              {preflightWarnings.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
                  {preflightWarnings.slice(0, 4).map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              )}
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-border-default px-3 py-2 text-sm hover:bg-surface-muted">Cancel</button>
          <button onClick={handleGenerate} disabled={disabled} className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {disabled ? "Generating…" : "Generate Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
