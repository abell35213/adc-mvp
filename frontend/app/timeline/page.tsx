"use client";

import MainLayout from "@/components/MainLayout";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getIncident, listIncidents, type EventSummary } from "@/lib/api";

const TIMELINE_POLL_MS = 10000;
const MAX_EVENTS = 250;

interface FeedEvent extends EventSummary {
  incident_id: string;
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function friendlyEventType(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function TimelinePage() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const incidents = await listIncidents();
        const detailResults = await Promise.allSettled(
          incidents.map((incident) => getIncident(incident.incident_id))
        );
        const details = detailResults
          .filter(
            (result): result is PromiseFulfilledResult<Awaited<ReturnType<typeof getIncident>>> =>
              result.status === "fulfilled"
          )
          .map((result) => result.value);
        const failedCount = detailResults.length - details.length;

        const allEvents = details
          .flatMap((incident) =>
            incident.timeline.map((event) => ({
              ...event,
              incident_id: incident.incident_id,
            }))
          )
          .sort(
            (a, b) =>
              new Date(b.occurred_at_utc).getTime() -
              new Date(a.occurred_at_utc).getTime()
          )
          .slice(0, MAX_EVENTS);

        if (!cancelled) {
          if (details.length > 0 || incidents.length === 0) {
            setEvents(allEvents);
          }
          if (failedCount > 0) {
            setError(
              `Loaded ${details.length} of ${detailResults.length} incidents. ${failedCount} failed to refresh.`
            );
          } else {
            setError("");
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load event timeline"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void refresh();
    const interval = window.setInterval(() => {
      void refresh();
    }, TIMELINE_POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const groupedCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      counts.set(event.event_type, (counts.get(event.event_type) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
  }, [events]);

  return (
    <MainLayout title="Live Timeline">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Live Timeline
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Cross-incident event feed powered by existing event data. This view
            refreshes every {TIMELINE_POLL_MS / 1000}s while streaming support is
            planned next.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="rounded border border-blue-600 px-3 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-gray-700"
        >
          Back to dashboard
        </Link>
      </div>

      {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded border bg-white p-3 text-sm shadow dark:border-gray-700 dark:bg-gray-800">
          <p className="text-gray-500">Events loaded</p>
          <p className="text-xl font-bold text-blue-600 dark:text-blue-400">{events.length}</p>
        </div>
        {groupedCounts.map(([eventType, count]) => (
          <div
            key={eventType}
            className="rounded border bg-white p-3 text-sm shadow dark:border-gray-700 dark:bg-gray-800"
          >
            <p className="text-gray-500">{friendlyEventType(eventType)}</p>
            <p className="text-xl font-bold text-blue-600 dark:text-blue-400">{count}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : events.length === 0 ? (
        <div className="rounded border border-dashed p-8 text-center text-gray-400 dark:border-gray-700">
          No incident events found yet.
        </div>
      ) : (
        <ol className="relative border-l border-gray-200 dark:border-gray-600">
          {events.map((event, index) => (
            <li key={`${event.incident_id}-${event.event_type}-${index}`} className="mb-5 ml-4">
              <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-blue-500 dark:border-gray-800" />
              <time className="mb-1 block text-xs text-gray-400">
                {formatTime(event.occurred_at_utc)}
              </time>
              <p className="text-sm font-medium text-gray-900 dark:text-white">
                {friendlyEventType(event.event_type)}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Incident{" "}
                <Link
                  className="text-blue-600 hover:underline dark:text-blue-400"
                  href={`/incidents/${event.incident_id}`}
                >
                  {event.incident_id.slice(0, 8)}…
                </Link>
                {" · "}
                Actor: {event.actor_type}
              </p>
            </li>
          ))}
        </ol>
      )}
    </MainLayout>
  );
}
