import {
  AvatarChip,
  DataTableShell,
  MetricCard,
  ProgressRing,
  ReadinessBadge,
  SeverityBadge,
  StatusChip,
} from "@/components/data-display";
import { PageHeader, RightRailPanel, SectionCard, StickySidebar } from "@/components/layout";
import type { StatusTone } from "@/lib/design/tokens";

const tones: StatusTone[] = ["neutral", "info", "success", "warning", "critical"];
const sizes = ["sm", "md", "lg"] as const;
const readinessStatuses = ["not_started", "in_progress", "ready", "blocked"] as const;
const severities = ["low", "medium", "high", "critical"] as const;

export default function DesignSystemDemoPage() {
  return (
    <main className="space-y-6 p-6">
      <PageHeader
        eyebrow="Design system"
        title="Layout & data-display contracts"
        subtitle="Demo states for tones, sizes, and status variants"
        actions={<button className="rounded-md border border-border-default px-3 py-1 text-sm">Action</button>}
        meta={<span>Updated for Sprint component build-out.</span>}
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          <SectionCard title="MetricCard tones" description="Visual lock for all tones">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {tones.map((tone) => (
                <MetricCard
                  key={tone}
                  label={`Tone: ${tone}`}
                  value={tone === "critical" ? "3" : "42"}
                  tone={tone}
                  trend={{ label: "+6%", tone }}
                  helperText="Compared to yesterday"
                />
              ))}
            </div>
          </SectionCard>

          <SectionCard title="StatusChip sizes × tones" tone="info">
            <div className="space-y-3">
              {sizes.map((size) => (
                <div key={size} className="flex flex-wrap gap-2">
                  {tones.map((tone) => (
                    <StatusChip key={`${size}-${tone}`} label={`${size} • ${tone}`} tone={tone} size={size} />
                  ))}
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Readiness + Severity badges" tone="warning">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                {readinessStatuses.map((status) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">{status}</span>
                    <ReadinessBadge status={status} />
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                {severities.map((severity) => (
                  <div key={severity} className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">{severity}</span>
                    <SeverityBadge severity={severity} />
                  </div>
                ))}
              </div>
            </div>
          </SectionCard>

          <SectionCard title="AvatarChip + ProgressRing" tone="success">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                {sizes.map((size) => (
                  <AvatarChip key={size} name="Jordan Lee" subtitle={`${size} size`} size={size} />
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <ProgressRing value={18} tone="critical" size="sm" label="18%" />
                <ProgressRing value={62} tone="warning" size="md" label="62%" />
                <ProgressRing value={92} tone="success" size="lg" label="92%" />
              </div>
            </div>
          </SectionCard>

          <DataTableShell
            title="DataTableShell state"
            description="Normal and empty states"
            actions={<button className="rounded-md border border-border-default px-2 py-1 text-xs">Refresh</button>}
            columns={
              <tr>
                <th className="px-3 py-2">Case</th>
                <th className="px-3 py-2">Owner</th>
                <th className="px-3 py-2">Readiness</th>
              </tr>
            }
          >
            <tr>
              <td className="px-3 py-2">INC-1022</td>
              <td className="px-3 py-2">Jordan Lee</td>
              <td className="px-3 py-2"><ReadinessBadge status="in_progress" /></td>
            </tr>
          </DataTableShell>

          <DataTableShell
            title="DataTableShell empty"
            columns={
              <tr>
                <th className="px-3 py-2">Case</th>
              </tr>
            }
            isEmpty
            emptyState="No cases match current filters."
          >
            <tr />
          </DataTableShell>
        </div>

        <StickySidebar>
          <RightRailPanel title="Right rail panel" subtitle="Sticky support state">
            <p className="text-sm text-text-secondary">Use this rail for owner, readiness, and next action context.</p>
          </RightRailPanel>
        </StickySidebar>
      </div>
    </main>
  );
}
