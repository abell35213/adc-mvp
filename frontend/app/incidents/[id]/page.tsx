import IncidentDetailClient from "./IncidentDetailClient";

export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export default function IncidentDetailPage() {
  return <IncidentDetailClient />;
}
  
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import EvidenceTable from "@/components/EvidenceTable";
import Timeline from "@/components/Timeline";
import ExportPanel from "@/components/ExportPanel";
import {
  getIncident,
  requestExport,
  downloadExport,
  type IncidentDetail,
} from "@/lib/api";

/**
 * Incident detail page.  Fetches and displays detailed information
 * about a single incident, including evidence inventory, timeline of
 * events and export history.  Users can generate a court package
 * and download ready exports.  All content is wrapped in the
 * MainLayout for navigation consistency.
 */
export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  const incidentId = params?.id;

  useEffect(() => {
    if (!incidentId) return;
    setLoading(true);
    getIncident(incidentId)
      .then(setIncident)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [incidentId]);

  async function handleExport() {
    if (!incident) return;
    setExporting(true);
    try {
      await requestExport(incident.incident_id);
      // Refresh incident details to reflect new export status
      const updated = await getIncident(incident.incident_id);
      setIncident(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function handleDownload(exportId: string) {
    try {
      const result = await downloadExport(exportId);
      // Open the presigned URL in a new tab to trigger the download
      window.open(result.url, "_blank");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

  return (
    <MainLayout title="Incident Details">
      <div className="mb-4">
        <Link
          href="/incidents"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← Back to incidents
        </Link>
        {incident && (
          <h2 className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
            Incident {incident.incident_id.slice(0, 8)}…
          </h2>
        )}
      </div>

      {/* Error state */}
      {error && <p className="mb-4 text-red-600">{error}</p>}

      {/* Loading state */}
      {loading && <p className="text-gray-500">Loading incident…</p>}

      {/* Incident details */}
      {!loading && incident && (
        <div className="space-y-8">
          {/* Evidence Inventory */}
          <section>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              Evidence Inventory
            </h3>
            <EvidenceTable artifacts={incident.evidence_inventory} />
          </section>

          {/* Event Timeline */}
          <section>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              Event Timeline
            </h3>
            <Timeline events={incident.timeline} />
          </section>

          {/* Export Actions */}
          <section>
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-white">
              Export Evidence Package
            </h3>
            <ExportPanel
              exports={incident.export_status}
              onExport={handleExport}
              onDownload={handleDownload}
              exporting={exporting}
            />
          </section>
        </div>
      )}
    </MainLayout>
  );
}
