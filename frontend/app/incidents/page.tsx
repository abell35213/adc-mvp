"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MainLayout from "@/components/MainLayout";
import DocumentationCenter from "@/components/commercial/DocumentationCenter";
import { listIncidents, type Incident } from "@/lib/api";
import { statusBadgeClass, type StatusTone, designTokens } from "@/lib/design/tokens";
import { useAuth } from "@/lib/useAuth";

/**
 * Incident listing page.  Displays all incidents accessible to the
 * current user in a table with key metadata and progress indicators.
 * The page is wrapped in the MainLayout to provide a consistent
 * navigation bar.  Admin users see an Admin link in the nav bar via
 * MainLayout.  From each row users can navigate to a detailed view.
 */
export default function IncidentsPage() {
  const { user, loading: authLoading } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "waiting_driver" | "ready">("all");

  useEffect(() => {
    // Fetch the list of incidents once the user is available.
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

  const waitingCount = incidents.filter(isWaitingOnDriver).length;
  const visibleIncidents = incidents.filter((incident) => {
    if (filter === "waiting_driver") return isWaitingOnDriver(incident);
    if (filter === "ready") return !isWaitingOnDriver(incident);
    return true;
  });

  const filterClass = (isActive: boolean, tone: StatusTone) => {
    if (isActive) return `${statusBadgeClass(tone)} ring-1 ring-current`;
    return `${statusBadgeClass(tone)} opacity-80 hover:opacity-100`;
  };

  return (
    <MainLayout title="Incidents">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-text-primary">Incidents</h2>
        <p className="text-sm text-text-secondary">
          View and manage all recorded incidents. Monitor evidence capture and export status.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button onClick={() => setFilter("all")} className={filterClass(filter === "all", "info")}>
            All ({incidents.length})
          </button>
          <button
            onClick={() => setFilter("waiting_driver")}
            className={filterClass(filter === "waiting_driver", "warning")}
          >
            Waiting on driver ({waitingCount})
          </button>
          <button onClick={() => setFilter("ready")} className={filterClass(filter === "ready", "success")}>
            Driver action complete ({incidents.length - waitingCount})
          </button>
        </div>
      </div>

      {(loading || authLoading) && <p className="text-text-muted">Loading…</p>}
      {error && <p className="text-status-critical">{error}</p>}

      {!loading && incidents.length === 0 && <p className="text-text-muted">No incidents found.</p>}
      {!loading && incidents.length > 0 && visibleIncidents.length === 0 && (
        <p className="text-text-muted">No incidents match the selected filter.</p>
      )}

      {!loading && visibleIncidents.length > 0 && (
        <div className={`${designTokens.surface.elevated} overflow-hidden`}>
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-muted text-text-secondary">
              <tr>
                <th className="px-4 py-3 font-medium">Incident ID</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Vehicle</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {visibleIncidents.map((inc) => {
                const captured = inc.evidence_captured ?? 0;
                const total = inc.evidence_total ?? 0;
                const pct = total > 0 ? Math.round((captured / total) * 100) : 0;
                const waitingOnDriver = isWaitingOnDriver(inc);
                return (
                  <tr key={inc.incident_id} className="hover:bg-surface-muted/70">
                    <td className="px-4 py-3">
                      <Link href={`/incidents/${inc.incident_id}`} className={`font-mono ${designTokens.accent.text}`}>
                        {inc.incident_id.slice(0, 8)}…
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{formatTime(inc.created_at_utc)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-text-secondary">{inc.adc_vehicle_id ?? "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={statusBadgeClass(statusTone(inc.status))}>{friendlyStatus(inc.status)}</span>
                        {waitingOnDriver && <span className={statusBadgeClass("warning")}>Waiting on driver</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-20 overflow-hidden rounded-full bg-accent-soft">
                          <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-text-muted">{captured}/{total}</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
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
