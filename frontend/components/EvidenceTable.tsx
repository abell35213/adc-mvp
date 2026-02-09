/** Evidence inventory table component. */

"use client";

import { type ArtifactSummary } from "@/lib/api";

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

function statusBadge(status: string) {
  if (status === "captured") return "bg-green-100 text-green-800";
  if (status === "unavailable") return "bg-red-100 text-red-800";
  if (status === "pending") return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-800";
}

function statusLabel(status: string): string {
  if (status === "captured") return "Captured";
  if (status === "unavailable") return "Unavailable";
  if (status === "pending") return "Pending";
  return status;
}

interface EvidenceTableProps {
  artifacts: ArtifactSummary[];
}

export default function EvidenceTable({ artifacts }: EvidenceTableProps) {
  const artifactMap = new Map<string, ArtifactSummary>();
  for (const a of artifacts) {
    artifactMap.set(a.artifact_type, a);
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-gray-50 dark:bg-gray-700">
          <tr>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">Evidence Type</th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">Status</th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">Captured Time</th>
            <th className="px-4 py-2 font-medium text-gray-600 dark:text-gray-300">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y dark:divide-gray-700">
          {EVIDENCE_TYPES.map(({ type, label }) => {
            const art = artifactMap.get(type);
            const status = art?.status ?? "pending";
            return (
              <tr key={type}>
                <td className="px-4 py-2 font-medium text-gray-800 dark:text-gray-200">{label}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(status)}`}>
                    {statusLabel(status)}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{formatTime(art?.captured_at_utc)}</td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{art?.unavailable_reason ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
