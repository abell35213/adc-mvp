"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import MainLayout from "@/components/MainLayout";
import { getIncident, listIncidents, type IncidentDetail } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

const DASHBOARD_POLL_MS = 15000;

function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const minutes = Math.floor(ms / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  return `${minutes}m`;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [incidentDetails, setIncidentDetails] = useState<IncidentDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadDashboard = async () => {
      try {
        const incidents = await listIncidents();
        const details = await Promise.all(
          incidents.map((incident) => getIncident(incident.incident_id))
        );
        if (!cancelled) {
          setIncidentDetails(details);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load KPIs");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadDashboard();
    const interval = window.setInterval(() => {
      void loadDashboard();
    }, DASHBOARD_POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const kpis = useMemo(() => {
    const now = Date.now();
    let captured = 0;
    let unavailable = 0;
    let pending = 0;

    let exportsQueued = 0;
    let exportsReady = 0;
    let exportsFailed = 0;

    let followUpEligible = 0;
    let followUpComplete = 0;

    let incidentAgeTotalMs = 0;
    let incidentAgeCount = 0;

    let firstEvidenceLatencyTotalMs = 0;
    let firstEvidenceLatencyCount = 0;

    for (const incident of incidentDetails) {
      for (const artifact of incident.evidence_inventory) {
        if (artifact.status === "captured") captured += 1;
        else if (artifact.status === "unavailable") unavailable += 1;
        else pending += 1;
      }

      for (const exp of incident.export_status) {
        if (exp.status === "ready") exportsReady += 1;
        else if (exp.status === "failed") exportsFailed += 1;
        else exportsQueued += 1;
      }

      const eventTypes = new Set(incident.timeline.map((event) => event.event_type));
      if (eventTypes.has("incident_protocol_initiated")) {
        followUpEligible += 1;
        if (eventTypes.has("driver_instruction_acknowledged")) {
          followUpComplete += 1;
        }
      }

      if (incident.created_at_utc) {
        const createdMs = new Date(incident.created_at_utc).getTime();
        if (!Number.isNaN(createdMs)) {
          incidentAgeTotalMs += now - createdMs;
          incidentAgeCount += 1;
        }
      }

      const firstCapturedAt = incident.evidence_inventory
        .filter((artifact) => artifact.status === "captured" && artifact.captured_at_utc)
        .map((artifact) => new Date(artifact.captured_at_utc as string).getTime())
        .filter((time) => !Number.isNaN(time))
        .sort((a, b) => a - b)[0];

      if (incident.created_at_utc && firstCapturedAt) {
        const createdMs = new Date(incident.created_at_utc).getTime();
        if (!Number.isNaN(createdMs) && firstCapturedAt >= createdMs) {
          firstEvidenceLatencyTotalMs += firstCapturedAt - createdMs;
          firstEvidenceLatencyCount += 1;
        }
      }
    }

    const evidenceTotal = captured + unavailable + pending;
    const evidenceCompletionRate =
      evidenceTotal > 0 ? Math.round((captured / evidenceTotal) * 100) : null;

    return {
      incidentCount: incidentDetails.length,
      captured,
      unavailable,
      pending,
      evidenceTotal,
      evidenceCompletionRate,
      exportsQueued,
      exportsReady,
      exportsFailed,
      followUpEligible,
      followUpComplete,
      avgIncidentAgeMs:
        incidentAgeCount > 0 ? incidentAgeTotalMs / incidentAgeCount : null,
      avgFirstEvidenceLatencyMs:
        firstEvidenceLatencyCount > 0
          ? firstEvidenceLatencyTotalMs / firstEvidenceLatencyCount
          : null,
    };
  }, [incidentDetails]);

  return (
    <MainLayout title="Dashboard">
      <section className="relative overflow-hidden rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="absolute inset-0 -z-10 h-full w-full">
          <Image
            src="/hero.png"
            alt="Abstract dashboard background"
            fill
            priority
            style={{ objectFit: "cover", opacity: 0.2 }}
          />
        </div>
        <div className="p-8 sm:p-12">
          <h2 className="mb-4 text-3xl font-extrabold text-gray-900 dark:text-white">
            Simplify accident reporting and evidence management
          </h2>
          <p className="mb-6 max-w-2xl text-gray-600 dark:text-gray-300">
            The ADC platform helps fleets respond quickly, capture crucial
            evidence and prepare compliant exports. Stay on top of incidents
            with operational KPIs backed by event data.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              href="/incidents"
              className="rounded bg-blue-600 px-5 py-3 text-sm font-medium text-white hover:bg-blue-700"
            >
              View Incidents
            </Link>
            {user?.role === "admin" && (
              <Link
                href="/admin/driver-protocol"
                className="rounded border border-blue-600 px-5 py-3 text-sm font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-gray-700"
              >
                Admin Settings
              </Link>
            )}
          </div>
          {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
        </div>
      </section>

      <section className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Incidents
          </h3>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (
            <>
              <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
                {kpis.incidentCount}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Avg time since incident: {formatDuration(kpis.avgIncidentAgeMs ?? NaN)}
              </p>
            </>
          )}
          <Link
            href="/incidents"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            Go to incidents →
          </Link>
        </div>

        <div className="rounded-lg border bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Evidence Capture
          </h3>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (
            <>
              <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
                {kpis.evidenceCompletionRate ?? 0}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {kpis.captured} captured · {kpis.pending} pending · {kpis.unavailable} unavailable
              </p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Avg time to first evidence: {formatDuration(kpis.avgFirstEvidenceLatencyMs ?? NaN)}
              </p>
            </>
          )}
          <Link
            href="/incidents"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            Manage evidence →
          </Link>
        </div>

        <div className="rounded-lg border bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Exports
          </h3>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (
            <>
              <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
                {kpis.exportsQueued}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Queued {kpis.exportsQueued} · Ready {kpis.exportsReady} · Failed {kpis.exportsFailed}
              </p>
            </>
          )}
          <Link
            href="/exports"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            View exports →
          </Link>
        </div>

        {user?.role === "admin" && (
          <div className="rounded-lg border bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
              Vehicles
            </h3>
            <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
              Manage your fleet and QR codes. Add, edit or remove vehicles
              and rotate QR tokens.
            </p>
            <Link
              href="/vehicles"
              className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              Manage vehicles →
            </Link>
          </div>
        )}

        <div className="rounded-lg border bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Driver Follow-up
          </h3>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : kpis.followUpEligible > 0 ? (
            <>
              <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
                {Math.round((kpis.followUpComplete / kpis.followUpEligible) * 100)}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {kpis.followUpComplete}/{kpis.followUpEligible} protocol incidents acknowledged
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">No driver follow-up events available yet.</p>
          )}
          <Link
            href="/timeline"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            View timeline →
          </Link>
        </div>
      </section>
    </MainLayout>
  );
}
