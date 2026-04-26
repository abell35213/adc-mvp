import MetricCard from "@/components/data-display/MetricCard";
import type { CaseOpsSummaryMetrics } from "@/lib/api";

interface IncidentSummaryCardsProps {
  metrics: CaseOpsSummaryMetrics | null;
  loading: boolean;
}

function valueOrLoading(value: number | undefined, loading: boolean) {
  return loading ? "…" : value ?? 0;
}

export default function IncidentSummaryCards({
  metrics,
  loading,
}: IncidentSummaryCardsProps) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <MetricCard
        label="What's New"
        value={valueOrLoading(metrics?.open_incidents, loading)}
        tone="info"
        helperText="Open incidents that need active attention now."
      />
      <MetricCard
        label="Blocked"
        value={valueOrLoading(metrics?.blocked_incidents, loading)}
        tone="critical"
        helperText="Cases currently blocked by missing evidence or dependencies."
      />
      <MetricCard
        label="Ready for Export"
        value={valueOrLoading(metrics?.export_aging_incidents, loading)}
        tone="success"
        helperText="Incidents ready or aging in export-ready state."
      />
      <MetricCard
        label="Unassigned"
        value={valueOrLoading(metrics?.unassigned_incidents, loading)}
        tone="warning"
        helperText="Incidents without clear ownership."
      />
      <MetricCard
        label="Stalled"
        value={valueOrLoading(metrics?.stalled_incidents, loading)}
        tone="warning"
        helperText="No recent movement and at risk of delay."
      />
      <MetricCard
        label="Overdue Follow-Ups"
        value={valueOrLoading(metrics?.overdue_tasks, loading)}
        tone="critical"
        helperText="Follow-up tasks past due and blocking readiness."
      />
    </section>
  );
}
