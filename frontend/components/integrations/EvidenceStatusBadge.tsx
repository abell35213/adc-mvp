import React from "react";

export type EvidenceIntegrationStatus =
  | "requested"
  | "queued"
  | "in_progress"
  | "available"
  | "partial"
  | "unavailable"
  | "failed";

const STATUS_STYLES: Record<EvidenceIntegrationStatus, string> = {
  requested: "bg-slate-100 text-slate-700",
  queued: "bg-blue-100 text-blue-800",
  in_progress: "bg-indigo-100 text-indigo-800",
  available: "bg-green-100 text-green-800",
  partial: "bg-amber-100 text-amber-800",
  unavailable: "bg-red-100 text-red-800",
  failed: "bg-rose-100 text-rose-800",
};

const STATUS_LABELS: Record<EvidenceIntegrationStatus, string> = {
  requested: "Requested",
  queued: "Queued",
  in_progress: "In progress",
  available: "Available",
  partial: "Partial",
  unavailable: "Unavailable",
  failed: "Failed",
};

interface EvidenceStatusBadgeProps {
  status: EvidenceIntegrationStatus;
}

export default function EvidenceStatusBadge({ status }: EvidenceStatusBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
