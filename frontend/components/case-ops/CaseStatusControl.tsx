"use client";

const CASE_STATUSES = [
  "new",
  "awaiting_evidence",
  "in_review",
  "ready_for_export",
  "escalated",
  "closed",
] as const;

interface CaseStatusControlProps {
  caseStatus: string;
  onChange: (nextStatus: string) => Promise<void>;
}

export default function CaseStatusControl({ caseStatus, onChange }: CaseStatusControlProps) {
  return (
    <label className="flex flex-col gap-1 rounded-md border bg-gray-50 p-3 text-xs dark:bg-gray-900/40">
      <span className="text-gray-500">Case status</span>
      <select
        className="rounded border px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-900"
        value={caseStatus}
        onChange={(e) => void onChange(e.target.value)}
      >
        {CASE_STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>
    </label>
  );
}
