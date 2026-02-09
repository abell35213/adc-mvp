/** Timeline component for incident events. */

"use client";

import { type EventSummary } from "@/lib/api";

function friendlyEventType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const MAX_EVENTS = 50;

interface TimelineProps {
  events: EventSummary[];
}

export default function Timeline({ events }: TimelineProps) {
  if (!events || events.length === 0) {
    return <p className="text-sm text-gray-400">No events yet.</p>;
  }

  const displayed = events.slice(-MAX_EVENTS);

  return (
    <ol className="relative border-l border-gray-200 dark:border-gray-600">
      {displayed.map((ev, i) => (
        <li key={i} className="mb-4 ml-4">
          <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-blue-500 dark:border-gray-800" />
          <time className="mb-1 text-xs text-gray-400">{formatTime(ev.occurred_at_utc)}</time>
          <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
            {friendlyEventType(ev.event_type)}
          </p>
        </li>
      ))}
    </ol>
  );
}
