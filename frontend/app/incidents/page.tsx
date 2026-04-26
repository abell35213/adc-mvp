"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import DocumentationCenter from "@/components/commercial/DocumentationCenter";
import DataTableShell from "@/components/data-display/DataTableShell";
import PageHeader from "@/components/layout/PageHeader";
import { listIncidents, type Incident } from "@/lib/api";
import { statusBadgeClass, type StatusTone, designTokens } from "@/lib/design/tokens";
import { useAuth } from "@/lib/useAuth";

type SavedViewKey = "all" | "attention" | "driver_wait" | "ready";

interface IncidentFilters {
  status: "all" | "capturing" | "ready";
  owner: "all" | "assigned" | "unassigned";
  dateRange: "all" | "today" | "week";
  readiness:
    | "all"
    | "not_ready"
    | "conditionally_ready"
    | "ready_for_export"
    | "exported"
    | "closed";
  evidenceState: "all" | "missing" | "partial" | "complete";
}

const REFERENCE_NOW = Date.now();

const DEFAULT_FILTERS: IncidentFilters = {
  status: "all",
  owner: "all",
  dateRange: "all",
  readiness: "all",
  evidenceState: "all",
};

const SAVED_VIEW_LABELS: Record<SavedViewKey, string> = {
  all: "All incidents",
  attention: "Needs attention",
  driver_wait: "Waiting on driver",
  ready: "Ready for export",
};

export default function IncidentsPage() {
  const { user, loading: authLoading } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savedView, setSavedView] = useState<SavedViewKey>("all");
  const [filters, setFilters] = useState<IncidentFilters>(DEFAULT_FILTERS);

  useEffect(() => {
    if (!user) return;
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user]);

  function friendlyStatus(s: string): string {
    if (s === "evidence_capturing" || s === "open") return "Capturing Evidence";
    if (s === "ready" || s === "closed" || s === "export_ready") return "Export Ready";
    return "Ready for Export";
  }

  function statusTone(s: string): StatusTone {
    if (s === "evidence_capturing" || s === "open") return "warning";
    if (s === "ready" || s === "closed" || s === "export_ready") return "success";
    return "info";
  }

  function formatTime(iso?: string): string {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function isWaitingOnDriver(incident: Incident): boolean {
    const driverResponse = incident.driver_response;
    if (typeof driverResponse?.awaiting_driver_action === "boolean") {
      return driverResponse.awaiting_driver_action;
    }
    const notificationSent = Boolean(driverResponse?.notification_sent_at_utc);
    if (!notificationSent) return false;
    const acknowledged = Boolean(driverResponse?.acknowledged_at_utc);
    const uploadsComplete = Boolean(driverResponse?.uploads_complete);
    return !acknowledged || !uploadsComplete;
  }

  function isReady(incident: Incident): boolean {
    return ["ready", "closed", "export_ready"].includes(incident.status);
  }

  function ownerState(incident: Incident): "assigned" | "unassigned" {
    return incident.adc_driver_id ? "assigned" : "unassigned";
  }

  function evidenceState(incident: Incident): IncidentFilters["evidenceState"] {
    const captured = incident.evidence_captured ?? 0;
    const total = incident.evidence_total ?? 0;
    if (total === 0 || captured === 0) return "missing";
    if (captured < total) return "partial";
    return "complete";
  }

  function inDateWindow(incident: Incident, dateRange: IncidentFilters["dateRange"]) {
    if (dateRange === "all") return true;
    if (!incident.created_at_utc) return false;
    const created = new Date(incident.created_at_utc).getTime();
    const ageMs = REFERENCE_NOW - created;
    if (dateRange === "today") return ageMs <= 24 * 60 * 60 * 1000;
    return ageMs <= 7 * 24 * 60 * 60 * 1000;
  }

  const counts = useMemo(() => {
    const waitingDriver = incidents.filter(isWaitingOnDriver).length;
    const ready = incidents.filter(isReady).length;
    const attention = incidents.filter((incident) => !isReady(incident) || isWaitingOnDriver(incident)).length;
    return {
      waitingDriver,
      ready,
      attention,
      blocked: incidents.filter((incident) => (incident.readiness_state ?? "not_ready") === "not_ready").length,
      missingEvidence: incidents.filter((incident) => evidenceState(incident) === "missing").length,
    };
  }, [incidents]);

  const savedViews = useMemo(
    () => [
      { key: "all" as const, count: incidents.length },
      { key: "attention" as const, count: counts.attention },
      { key: "driver_wait" as const, count: counts.waitingDriver },
      { key: "ready" as const, count: counts.ready },
    ],
    [counts, incidents.length],
  );

  const visibleIncidents = incidents.filter((incident) => {
    if (savedView === "attention" && isReady(incident) && !isWaitingOnDriver(incident)) return false;
    if (savedView === "driver_wait" && !isWaitingOnDriver(incident)) return false;
    if (savedView === "ready" && !isReady(incident)) return false;

    if (filters.status === "capturing" && isReady(incident)) return false;
    if (filters.status === "ready" && !isReady(incident)) return false;

    if (filters.owner !== "all" && ownerState(incident) !== filters.owner) return false;
    if (!inDateWindow(incident, filters.dateRange)) return false;

    if (filters.readiness !== "all" && (incident.readiness_state ?? "not_ready") !== filters.readiness) {
      return false;
    }

    if (filters.evidenceState !== "all" && evidenceState(incident) !== filters.evidenceState) {
      return false;
    }

    return true;
  });

  return (
    <MainLayout title="Incidents">
      <div className="space-y-4">
        <PageHeader
          eyebrow="Case Operations"
          title="Incident Triage Queue"
          subtitle="Track attention, ownership, evidence completeness, and export readiness from one command surface."
          actions={(
            <Link
              href="/dashboard"
              className="rounded border border-status-info/40 bg-status-info-soft px-3 py-1.5 text-sm font-medium text-status-info hover:opacity-90"
            >
              Open command center
            </Link>
          )}
          meta={(
            <div className="flex flex-wrap items-center gap-3">
              <span className={statusBadgeClass("warning")}>Needs attention: {counts.attention}</span>
              <span className={statusBadgeClass("critical")}>Blocked readiness: {counts.blocked}</span>
              <span className={statusBadgeClass("success")}>Ready for export: {counts.ready}</span>
            </div>
          )}
        />

        <section className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
          <div className="flex flex-wrap items-center gap-2">
            {savedViews.map((view) => {
              const active = savedView === view.key;
              return (
                <button
                  key={view.key}
                  type="button"
                  onClick={() => setSavedView(view.key)}
                  className={[
                    "rounded-md px-3 py-1.5 text-sm font-medium transition",
                    active
                      ? "bg-status-info-soft text-status-info"
                      : "border border-border-subtle text-text-secondary hover:bg-surface-raised",
                  ].join(" ")}
                >
                  {SAVED_VIEW_LABELS[view.key]} <span className="ml-1 text-xs">({view.count})</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="rounded-lg border border-border-default bg-surface p-4 shadow-card">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-text-primary">Filter bar</h3>
            <button
              type="button"
              onClick={() => setFilters(DEFAULT_FILTERS)}
              className="rounded border border-border-default px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface-raised"
            >
              Reset filters
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <select
              value={filters.status}
              onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value as IncidentFilters["status"] }))}
              className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
            >
              <option value="all">Status: all</option>
              <option value="capturing">Capturing evidence</option>
              <option value="ready">Ready for export</option>
            </select>
            <select
              value={filters.owner}
              onChange={(event) => setFilters((current) => ({ ...current, owner: event.target.value as IncidentFilters["owner"] }))}
              className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
            >
              <option value="all">Owner: all</option>
              <option value="assigned">Assigned</option>
              <option value="unassigned">Unassigned</option>
            </select>
            <select
              value={filters.dateRange}
              onChange={(event) => setFilters((current) => ({ ...current, dateRange: event.target.value as IncidentFilters["dateRange"] }))}
              className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
            >
              <option value="all">Date: all time</option>
              <option value="today">Date: last 24 hours</option>
              <option value="week">Date: last 7 days</option>
            </select>
            <select
              value={filters.readiness}
              onChange={(event) => setFilters((current) => ({ ...current, readiness: event.target.value as IncidentFilters["readiness"] }))}
              className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
            >
              <option value="all">Readiness: all</option>
              <option value="ready">Readiness ready</option>
              <option value="blocked">Readiness blocked</option>
              <option value="not_ready">Readiness not ready</option>
            </select>
            <select
              value={filters.evidenceState}
              onChange={(event) => setFilters((current) => ({ ...current, evidenceState: event.target.value as IncidentFilters["evidenceState"] }))}
              className="rounded border border-border-default bg-surface px-3 py-2 text-sm"
            >
              <option value="all">Evidence: all</option>
              <option value="missing">Missing</option>
              <option value="partial">Partial</option>
              <option value="complete">Complete</option>
            </select>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border border-border-default bg-surface p-3 shadow-card">
            <p className="text-xs text-text-muted">Total incidents</p>
            <p className="text-2xl font-semibold text-text-primary">{incidents.length}</p>
          </div>
          <div className="rounded-lg border border-status-warning/30 bg-status-warning-soft/40 p-3 shadow-card">
            <p className="text-xs text-status-warning">Needs attention</p>
            <p className="text-2xl font-semibold text-text-primary">{counts.attention}</p>
          </div>
          <div className="rounded-lg border border-status-warning/30 bg-status-warning-soft/40 p-3 shadow-card">
            <p className="text-xs text-status-warning">Waiting on driver</p>
            <p className="text-2xl font-semibold text-text-primary">{counts.waitingDriver}</p>
          </div>
          <div className="rounded-lg border border-status-critical/30 bg-status-critical-soft/50 p-3 shadow-card">
            <p className="text-xs text-status-critical">Missing evidence</p>
            <p className="text-2xl font-semibold text-text-primary">{counts.missingEvidence}</p>
          </div>
          <div className="rounded-lg border border-status-success/30 bg-status-success-soft/50 p-3 shadow-card">
            <p className="text-xs text-status-success">Ready for export</p>
            <p className="text-2xl font-semibold text-text-primary">{counts.ready}</p>
          </div>
        </section>

        {(loading || authLoading) && <p className="text-text-muted">Loading…</p>}
        {error && <p className="text-status-critical">{error}</p>}

        {!loading && (
          <DataTableShell
            className="w-full"
            title="Incident table"
            description="Full queue with ownership, readiness blockers, and evidence movement."
            isEmpty={visibleIncidents.length === 0}
            emptyState="No incidents match the selected saved view and filters."
            columns={(
              <tr className="sticky top-0 z-10 bg-surface-muted">
                <th className="px-4 py-3 font-medium">Incident</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Readiness</th>
                <th className="px-4 py-3 font-medium">Evidence</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            )}
          >
            {visibleIncidents.map((incident) => {
              const captured = incident.evidence_captured ?? 0;
              const total = incident.evidence_total ?? 0;
              const pct = total > 0 ? Math.round((captured / total) * 100) : 0;
              const waitingOnDriver = isWaitingOnDriver(incident);
              const readiness = incident.readiness_state ?? "not_ready";

              return (
                <tr key={incident.incident_id} className="group hover:bg-surface-muted/70">
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      <Link href={`/incidents/${incident.incident_id}`} className={`font-mono font-semibold ${designTokens.accent.text}`}>
                        {incident.incident_id.slice(0, 8)}…
                      </Link>
                      <div className="text-xs text-text-secondary">
                        Driver {incident.adc_driver_id ?? "Unassigned"} · Unit {incident.adc_vehicle_id ?? "Unknown"}
                      </div>
                      <p className="text-xs text-text-muted">Recent activity: {formatTime(incident.driver_response?.notification_sent_at_utc ?? incident.created_at_utc)}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className={statusBadgeClass(statusTone(incident.status))}>{friendlyStatus(incident.status)}</span>
                      {waitingOnDriver ? <span className={statusBadgeClass("warning")}>Waiting on driver</span> : null}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={statusBadgeClass(readiness === "ready" ? "success" : readiness === "blocked" ? "critical" : "warning")}>
                      {readiness.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-accent-soft">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-text-muted">{captured}/{total}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    <div className="flex items-center justify-between gap-2">
                      <span>{formatTime(incident.created_at_utc)}</span>
                      <div className="hidden gap-1 opacity-0 transition group-hover:flex group-hover:opacity-100">
                        <Link href={`/incidents/${incident.incident_id}`} className="rounded border border-border-default px-2 py-1 text-xs text-text-secondary hover:bg-surface-raised">
                          Open
                        </Link>
                        <Link href="/exports" className="rounded border border-status-success/40 bg-status-success-soft px-2 py-1 text-xs text-status-success hover:opacity-90">
                          Export
                        </Link>
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </DataTableShell>
        )}

        <DocumentationCenter
          title="Incident workflow help"
          docs={[
            {
              title: "Onboarding readiness",
              href: "/onboarding",
              description: "Use launch checklist status to identify unresolved setup blockers.",
            },
            {
              title: "Export handoff",
              href: "/exports",
              description: "Review package completeness and legal download audit before sharing.",
            },
            {
              title: "Trust center",
              href: "/trust",
              description: "Reference security and compliance controls used for evidence handling.",
            },
          ]}
        />
      </div>
    </MainLayout>
  );
}
