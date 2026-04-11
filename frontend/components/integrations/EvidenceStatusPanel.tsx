import Link from "next/link";
import EvidenceStatusBadge, { type EvidenceIntegrationStatus } from "@/components/integrations/EvidenceStatusBadge";

export interface EvidenceStatusItem {
  key: string;
  evidenceType: string;
  status: EvidenceIntegrationStatus;
  requestedWindow?: string | null;
  operationUrl?: string | null;
  artifactUrl?: string | null;
  missingReason?: string | null;
  retryAvailable?: boolean;
}

interface EvidenceStatusPanelProps {
  items: EvidenceStatusItem[];
  onRetry?: (item: EvidenceStatusItem) => void;
  retrying?: boolean;
}

export default function EvidenceStatusPanel({
  items,
  onRetry,
  retrying = false,
}: EvidenceStatusPanelProps) {
  if (items.length === 0) {
    return <p className="text-xs text-gray-500">No integration evidence status available yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-3 py-2 text-left">Evidence type</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-left">Requested window</th>
            <th className="px-3 py-2 text-left">Links</th>
            <th className="px-3 py-2 text-left">Missing reason</th>
            <th className="px-3 py-2 text-left">Retry</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white align-top">
          {items.map((item) => (
            <tr key={item.key}>
              <td className="px-3 py-2 text-gray-900">{item.evidenceType}</td>
              <td className="px-3 py-2">
                <EvidenceStatusBadge status={item.status} />
              </td>
              <td className="px-3 py-2 text-gray-700">{item.requestedWindow ?? "—"}</td>
              <td className="px-3 py-2 text-xs">
                <div className="flex flex-col gap-1">
                  {item.operationUrl ? (
                    <Link href={item.operationUrl} className="text-blue-600 hover:underline">
                      Operation
                    </Link>
                  ) : (
                    <span className="text-gray-400">Operation —</span>
                  )}
                  {item.artifactUrl ? (
                    <Link href={item.artifactUrl} className="text-blue-600 hover:underline">
                      Artifact
                    </Link>
                  ) : (
                    <span className="text-gray-400">Artifact —</span>
                  )}
                </div>
              </td>
              <td className="px-3 py-2 text-gray-700">{item.missingReason ?? "—"}</td>
              <td className="px-3 py-2">
                {item.retryAvailable && onRetry ? (
                  <button
                    onClick={() => onRetry(item)}
                    disabled={retrying}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
                  >
                    Retry
                  </button>
                ) : (
                  <span className="text-xs text-gray-400">Not available</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
