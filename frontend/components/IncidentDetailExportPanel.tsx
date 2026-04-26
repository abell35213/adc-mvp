import ExportPanelCore from "@/components/exports/IncidentDetailExportPanel";
import type { ArtifactSummary, ExportSummary } from "@/lib/api";

interface IncidentDetailExportPanelProps {
  incidentId: string;
  exports: ExportSummary[];
  artifacts: ArtifactSummary[];
  onExportsChanged: () => Promise<void>;
}

export default function IncidentDetailExportPanel(props: IncidentDetailExportPanelProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Export readiness & actions</h3>
      <p className="mt-1 text-xs text-gray-500">Confirm readiness before creating and downloading export packets.</p>
      <div className="mt-3">
        <ExportPanelCore {...props} />
      </div>
    </section>
  );
}
