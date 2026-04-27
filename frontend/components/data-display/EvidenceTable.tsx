/** Evidence inventory table component.
 *
 * This client component renders a table summarising the evidence
 * artifacts associated with an incident.  It accepts a list of
 * ArtifactSummary objects returned from the backend and displays a
 * consistent set of evidence types.  Any missing artifact is
 * interpreted as pending.  Captured artifacts show their capture
 * time and status, unavailable artifacts show a reason, and pending
 * artifacts display placeholders.
 */

"use client";

import { type ArtifactSummary } from "@/lib/api";
import { getEvidenceMeta, getStatusBadgeClass } from "@/lib/status";

// The canonical list of evidence types supported by the platform.  If
// additional types are added server‑side they should be reflected here
// for a complete inventory display.
export const EVIDENCE_TYPES: { type: string; label: string }[] = [
  { type: "dashcam_road", label: "Dashcam Road" },
  { type: "dashcam_driver", label: "Dashcam Driver" },
  { type: "eld_duty_status", label: "ELD Duty Status" },
  { type: "gps_trace", label: "GPS Trace" },
  { type: "safety_events", label: "Safety Events" },
  { type: "vehicle_state", label: "Vehicle State" },
  { type: "evidence_inventory", label: "Evidence Inventory" },
  { type: "chain_of_custody", label: "Chain of Custody" },
];

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


interface EvidenceTableProps {
  artifacts: ArtifactSummary[];
}

interface ArtifactDetail extends ArtifactSummary {
  artifact_hash?: string | null;
  source_provider?: string | null;
  capture_method?: string | null;
  remediation_state?: string | null;
  collected_at_utc?: string | null;
  validated_at_utc?: string | null;
  exported_at_utc?: string | null;
  downloaded_at_utc?: string | null;
}

function toTitleCase(value?: string | null): string {
  if (!value) return "—";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function EvidenceTable({ artifacts }: EvidenceTableProps) {
  const artifactMap = new Map<string, ArtifactDetail>();
  for (const a of artifacts) {
    artifactMap.set(a.artifact_type, a as ArtifactDetail);
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-gray-50 dark:bg-gray-700">
          <tr>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Evidence Type
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Status
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Captured Time
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Artifact Hash
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Source Provider
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Capture Method
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Custody Timestamps
            </th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
              Availability Notes
            </th>
          </tr>
        </thead>
        <tbody className="divide-y dark:divide-gray-700">
          {EVIDENCE_TYPES.map(({ type, label }) => {
            const art = artifactMap.get(type);
            const status = art?.status ?? "pending";
            const evidenceMeta = getEvidenceMeta(status);
            return (
              <tr
                key={type}
                className={status === "unavailable" ? "bg-red-50/60" : undefined}
              >
                <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-200">
                  {label}
                </td>
                <td className="px-4 py-2">
                  <span className={getStatusBadgeClass(evidenceMeta.tone)}>
                    {evidenceMeta.label}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                  {formatTime(art?.captured_at_utc)}
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                  {art?.artifact_hash ? (
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                      {art.artifact_hash}
                    </code>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                  {toTitleCase(art?.source_provider)}
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                  {toTitleCase(art?.capture_method)}
                </td>
                <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">
                  <div className="space-y-1">
                    <p>Collected: {formatTime(art?.collected_at_utc ?? art?.captured_at_utc)}</p>
                    <p>Validated: {formatTime(art?.validated_at_utc)}</p>
                    <p>Exported: {formatTime(art?.exported_at_utc)}</p>
                    <p>Downloaded: {formatTime(art?.downloaded_at_utc)}</p>
                  </div>
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">
                  {status === "unavailable" ? (
                    <div className="space-y-1 text-xs">
                      <p>
                        <span className="font-medium text-red-700">Reason:</span>{" "}
                        {art?.unavailable_reason ?? "Unknown"}
                      </p>
                      <p>
                        <span className="font-medium text-red-700">
                          Remediation:
                        </span>{" "}
                        {toTitleCase(art?.remediation_state)}
                      </p>
                    </div>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
