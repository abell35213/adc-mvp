import SectionCard from "@/components/layout/SectionCard";
import type { CaseOpsAlerts } from "@/lib/api";

interface AlertsPanelProps {
  alerts: CaseOpsAlerts | null;
  loading: boolean;
  error: string;
}

const ALERT_ROWS: Array<{ key: keyof CaseOpsAlerts; label: string }> = [
  { key: "blocked", label: "Blocked incidents" },
  { key: "overdue", label: "Overdue follow-ups" },
  { key: "stalled", label: "Stalled incidents" },
  { key: "unassigned", label: "Unassigned incidents" },
  { key: "export_aging", label: "Export aging" },
];

export default function AlertsPanel({ alerts, loading, error }: AlertsPanelProps) {
  return (
    <SectionCard
      title="Critical Alerts"
      tone="critical"
      description="See what is blocked or at immediate risk first."
    >
      {loading ? <p className="text-sm text-text-secondary">Loading alerts…</p> : null}
      {error ? <p className="text-sm text-status-critical">{error}</p> : null}
      {!loading && !error && alerts ? (
        <ul className="space-y-2 text-sm">
          {ALERT_ROWS.map((row) => (
            <li key={row.key} className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
              <span className="text-text-secondary">{row.label}</span>
              <span className="text-sm font-semibold text-text-primary">{alerts[row.key]}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </SectionCard>
  );
}
