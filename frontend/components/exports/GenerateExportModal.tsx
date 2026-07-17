"use client";

import { useMemo, useState } from "react";
import type { ExportType } from "@/lib/api";
import { Alert, Button, Card, CardContent, EmptyState, FormField, Modal, Select, StatusBadge } from "@/components/ui";

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
  incidentLabel?: string;
  warningCount?: number;
  preflightPendingCount?: number;
  preflightUnavailableCount?: number;
  preflightWarnings?: string[];
}

const EXPORT_TYPES: Array<{ value: ExportType; label: string; profileId: ExportOptions["profile_id"]; description: string }> = [
  { value: "court_defense", label: "Court defense packet", profileId: "court_defense_v1", description: "Complete litigation-ready packet with evidence inventory and telemetry." },
  { value: "insurer_packet", label: "Insurer packet", profileId: "insurer_packet_v1", description: "Claim-focused packet with media and driver statement." },
  { value: "internal_review", label: "Internal review", profileId: "internal_review_v1", description: "Internal operational review with available source records." },
  { value: "compliance_audit", label: "Compliance audit", profileId: "compliance_audit_v1", description: "Compliance-focused document with telemetry and audit context." },
];

const PROFILE_DEFAULTS: Record<ExportType, Omit<ExportOptions, "profile_id">> = {
  court_defense: { include_media: true, include_raw_telemetry: true, include_driver_statement: true },
  insurer_packet: { include_media: true, include_raw_telemetry: false, include_driver_statement: true },
  internal_review: { include_media: true, include_raw_telemetry: true, include_driver_statement: true },
  compliance_audit: { include_media: false, include_raw_telemetry: true, include_driver_statement: false },
};

function defaultOptionsForType(type: ExportType): ExportOptions {
  const profileId = EXPORT_TYPES.find((t) => t.value === type)?.profileId ?? "court_defense_v1";
  return { profile_id: profileId, ...PROFILE_DEFAULTS[type] };
}

export default function GenerateExportModal({
  open,
  onClose,
  onSubmit,
  disabled = false,
  incidentLabel = "Selected case",
  warningCount = 0,
  preflightPendingCount = 0,
  preflightUnavailableCount = 0,
  preflightWarnings = [],
}: GenerateExportModalProps) {
  const [exportType, setExportType] = useState<ExportType>("court_defense");
  const [options, setOptions] = useState<ExportOptions>(() => defaultOptionsForType("court_defense"));
  const selectedType = EXPORT_TYPES.find((type) => type.value === exportType) ?? EXPORT_TYPES[0];
  const readinessTone = preflightUnavailableCount > 0 ? "warning" : preflightPendingCount > 0 || warningCount > 0 ? "informational" : "success";
  const readinessLabel = preflightUnavailableCount > 0 ? "Can generate with blockers" : preflightPendingCount > 0 || warningCount > 0 ? "Review warnings" : "Ready to generate";

  const includedSections = useMemo(() => {
    const sections = ["Evidence inventory snapshot", "Chain-of-custody timeline", "Integrity verification report"];
    if (options.include_media) sections.push("Incident media bundle");
    if (options.include_raw_telemetry) sections.push("Raw telemetry records");
    if (options.include_driver_statement) sections.push("Driver statement and protocol logs");
    return sections;
  }, [options]);

  async function handleGenerate() {
    if (disabled) return;
    await onSubmit({ exportType, options });
  }

  return (
    <Modal
    open={open}
    onClose={onClose}
    title="Generate document"
    description="Review readiness and choose the document type before starting generation."
    size="lg"
    footer={<><Button variant="secondary" onClick={onClose} disabled={disabled}>Cancel</Button><Button onClick={handleGenerate} loading={disabled} loadingLabel="Starting generation">Generate document</Button></>}
    >
    <div className="space-y-4">
      <Card><CardContent className="grid gap-3 md:grid-cols-3">
          <div><p className="text-xs font-medium text-text-muted">Selected incident</p><p className="mt-1 text-sm font-semibold text-text-primary">{incidentLabel}</p></div>
          <div><p className="text-xs font-medium text-text-muted">Document type</p><p className="mt-1 text-sm font-semibold text-text-primary">{selectedType.label}</p></div>
          <div><p className="text-xs font-medium text-text-muted">Readiness</p><div className="mt-1"><StatusBadge tone={readinessTone}>{readinessLabel}</StatusBadge></div></div>
        </CardContent></Card>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-4">
            <FormField id="export-type" label="Document type" helpText={selectedType.description}>
              <Select value={exportType} onChange={(e) => { const newType = e.target.value as ExportType; setExportType(newType); setOptions(defaultOptionsForType(newType)); }}>
                {EXPORT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
              </Select>
            </FormField>
            <fieldset className="rounded-lg border border-border-default bg-surface-muted p-3">
              <legend className="px-1 text-sm font-medium text-text-secondary">Included evidence sections</legend>
              <div className="mt-2 space-y-2 text-sm text-text-primary">
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_media} onChange={(e) => setOptions((prev) => ({ ...prev, include_media: e.target.checked }))} /> Include media</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_raw_telemetry} onChange={(e) => setOptions((prev) => ({ ...prev, include_raw_telemetry: e.target.checked }))} /> Include telemetry</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={options.include_driver_statement} onChange={(e) => setOptions((prev) => ({ ...prev, include_driver_statement: e.target.checked }))} /> Include driver statement</label>
              </div>
            </fieldset>
          </div>

          <div className="space-y-4">
            <Card><CardContent><p className="text-sm font-medium text-text-primary">Manifest preview</p><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-secondary">{includedSections.map((section) => <li key={section}>{section}</li>)}</ul></CardContent></Card>
            {(preflightPendingCount > 0 || preflightUnavailableCount > 0 || warningCount > 0) ? <Alert tone="warning" title="Review evidence readiness" description={`Pending evidence: ${preflightPendingCount}. Blocking or unavailable items: ${preflightUnavailableCount}. Recent warnings: ${warningCount}.`} /> : <Alert tone="success" title="No evidence blockers detected" description="The available preflight data does not show missing evidence blockers." />}
            {preflightWarnings.length > 0 ? <ul className="rounded-lg border border-border-default bg-surface p-3 text-sm text-text-secondary">{preflightWarnings.slice(0, 4).map((warning) => <li key={warning} className="py-1">{warning}</li>)}</ul> : <EmptyState title="No blocking requirements listed" message="Generation will start a queued background workflow and update the document list when ready." />}
          </div>
        </div>
        <Alert tone="informational" title="What happens next" description="ADC will create one generation request, queue document assembly, and return status updates in the Documents tab. Do not refresh or submit again while generation is starting." />
      </div>
    </Modal>
  );
}
