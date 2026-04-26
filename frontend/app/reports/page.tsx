"use client";

import { useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import ReportSummaryCards from "@/components/reports/ReportSummaryCards";

type ReportTabKey = "attention" | "readiness" | "sla";

interface TrendPoint {
  label: string;
  value: number;
}

interface ReportRow {
  queue: string;
  owner: string;
  unresolved: number;
  blocked: number;
  ready: number;
  nextAction: string;
}

const REPORT_TABS: Array<{ key: ReportTabKey; label: string }> = [
  { key: "attention", label: "Incident attention" },
  { key: "readiness", label: "Export readiness" },
  { key: "sla", label: "Support SLA" },
];

const REPORT_DATA: Record<
  ReportTabKey,
  {
    subtitle: string;
    cards: Array<{ label: string; value: string; detail: string; tone?: "success" | "warning" | "critical" }>;
    trend: TrendPoint[];
    rows: ReportRow[];
  }
> = {
  attention: {
    subtitle: "Track where operators should focus first, which queues are blocked, and what can wait.",
    cards: [
      { label: "Needs action now", value: "28", detail: "+5 since yesterday", tone: "critical" },
      { label: "Unassigned incidents", value: "9", detail: "Owner reassignment pending", tone: "warning" },
      { label: "Awaiting driver response", value: "14", detail: "Median wait: 3.1h" },
      { label: "Resolved today", value: "31", detail: "Outpaced intake by 12%", tone: "success" },
    ],
    trend: [
      { label: "Mon", value: 18 },
      { label: "Tue", value: 24 },
      { label: "Wed", value: 20 },
      { label: "Thu", value: 27 },
      { label: "Fri", value: 28 },
    ],
    rows: [
      { queue: "High-severity collisions", owner: "Ops Alpha", unresolved: 7, blocked: 3, ready: 2, nextAction: "Escalate evidence chase" },
      { queue: "Late-night incidents", owner: "Ops Bravo", unresolved: 11, blocked: 2, ready: 5, nextAction: "Rebalance on-call coverage" },
      { queue: "Insurance escalations", owner: "Ops Delta", unresolved: 10, blocked: 4, ready: 1, nextAction: "Assign legal reviewer" },
    ],
  },
  readiness: {
    subtitle: "Show what is export-ready, what is blocked, and exactly where evidence is incomplete.",
    cards: [
      { label: "Ready for export", value: "64%", detail: "+4 points week-over-week", tone: "success" },
      { label: "Blocked by missing media", value: "12", detail: "Mostly witness uploads", tone: "critical" },
      { label: "Conditionally ready", value: "17", detail: "Require owner sign-off", tone: "warning" },
      { label: "Avg readiness time", value: "19.4h", detail: "From incident open to ready" },
    ],
    trend: [
      { label: "Mon", value: 52 },
      { label: "Tue", value: 55 },
      { label: "Wed", value: 58 },
      { label: "Thu", value: 61 },
      { label: "Fri", value: 64 },
    ],
    rows: [
      { queue: "Commercial fleet", owner: "Readiness West", unresolved: 15, blocked: 5, ready: 20, nextAction: "Close photo evidence gaps" },
      { queue: "Campus mobility", owner: "Readiness East", unresolved: 8, blocked: 2, ready: 14, nextAction: "Finalize supervisor review" },
      { queue: "Airport operations", owner: "Readiness Central", unresolved: 9, blocked: 3, ready: 9, nextAction: "Trigger automated reminders" },
    ],
  },
  sla: {
    subtitle: "Monitor response performance and identify queues at risk of breaching support commitments.",
    cards: [
      { label: "SLA attainment", value: "98.9%", detail: "30-day rolling window", tone: "success" },
      { label: "At-risk queues", value: "3", detail: "2 due to staffing gaps", tone: "warning" },
      { label: "SLA breaches", value: "2", detail: "Both recovered under 1 hour", tone: "critical" },
      { label: "Median first response", value: "11m", detail: "Down from 14m last week" },
    ],
    trend: [
      { label: "Mon", value: 97 },
      { label: "Tue", value: 99 },
      { label: "Wed", value: 98 },
      { label: "Thu", value: 99 },
      { label: "Fri", value: 99 },
    ],
    rows: [
      { queue: "Enterprise support", owner: "Support Pod A", unresolved: 13, blocked: 1, ready: 11, nextAction: "Maintain weekend coverage" },
      { queue: "Municipal contracts", owner: "Support Pod B", unresolved: 9, blocked: 2, ready: 8, nextAction: "Cross-train escalation lane" },
      { queue: "SMB onboarding", owner: "Support Pod C", unresolved: 6, blocked: 1, ready: 12, nextAction: "Automate first-touch routing" },
    ],
  },
};

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<ReportTabKey>("attention");
  const activeReport = REPORT_DATA[activeTab];

  const maxTrendValue = useMemo(
    () => Math.max(...activeReport.trend.map((point) => point.value), 1),
    [activeReport.trend],
  );

  return (
    <MainLayout title="Reports">
      <div className="space-y-4">
        <div className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
          <h2 className="text-xl font-semibold text-text-primary">Operations reporting overview</h2>
          <p className="mt-1 text-sm text-text-secondary">{activeReport.subtitle}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {REPORT_TABS.map((tab) => {
              const active = tab.key === activeTab;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={[
                    "rounded-md px-3 py-1.5 text-sm font-medium transition",
                    active
                      ? "bg-status-info-soft text-status-info"
                      : "border border-border-subtle text-text-secondary hover:bg-surface-raised",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <ReportSummaryCards items={activeReport.cards} />

        <section className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <article className="rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
            <h3 className="text-base font-semibold text-text-primary">Primary trend</h3>
            <p className="mt-1 text-sm text-text-secondary">Five-day performance snapshot for the selected report.</p>
            <div className="mt-4 space-y-3">
              {activeReport.trend.map((point) => (
                <div key={point.label}>
                  <div className="mb-1 flex items-center justify-between text-xs text-text-muted">
                    <span>{point.label}</span>
                    <span>{point.value}</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-raised">
                    <div
                      className="h-2 rounded-full bg-status-info"
                      style={{ width: `${(point.value / maxTrendValue) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
            <h3 className="text-base font-semibold text-text-primary">Supporting queue table</h3>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-text-muted">
                  <tr>
                    <th className="pb-2 pr-3">Queue</th>
                    <th className="pb-2 pr-3">Owner</th>
                    <th className="pb-2 pr-3">Unresolved</th>
                    <th className="pb-2 pr-3">Blocked</th>
                    <th className="pb-2 pr-3">Ready</th>
                    <th className="pb-2">Next action</th>
                  </tr>
                </thead>
                <tbody>
                  {activeReport.rows.map((row) => (
                    <tr key={row.queue} className="border-t border-border-subtle text-text-secondary">
                      <td className="py-2 pr-3 font-medium text-text-primary">{row.queue}</td>
                      <td className="py-2 pr-3">{row.owner}</td>
                      <td className="py-2 pr-3">{row.unresolved}</td>
                      <td className="py-2 pr-3">{row.blocked}</td>
                      <td className="py-2 pr-3">{row.ready}</td>
                      <td className="py-2">{row.nextAction}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      </div>
    </MainLayout>
  );
}
