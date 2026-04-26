"use client";

import { useState } from "react";

const CASE_STATUSES = [
  "new",
  "awaiting_evidence",
  "awaiting_follow_up",
  "in_review",
  "ready_for_export",
  "exported",
  "escalated",
  "closed",
] as const;

interface CaseStatusControlProps {
  caseStatus: string;
  onChange: (nextStatus: string) => Promise<void>;
}

export default function CaseStatusControl({ caseStatus, onChange }: CaseStatusControlProps) {
  const [busy, setBusy] = useState(false);

  return (
    <label className="flex flex-col gap-1 rounded-lg border bg-white p-4 text-xs shadow-sm">
      <span className="font-semibold uppercase tracking-wide text-gray-500">Case status</span>
      <select
        className="rounded border border-gray-300 px-2 py-1.5 text-sm text-gray-900 disabled:opacity-60"
        value={caseStatus}
        disabled={busy}
        onChange={async (e) => {
          setBusy(true);
          try {
            await onChange(e.target.value);
          } finally {
            setBusy(false);
          }
        }}
      >
        {CASE_STATUSES.map((status) => (
          <option key={status} value={status}>
            {status.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}
