/** Timeline component for incident events.
 *
 * This client component displays a chronological list of events for a
 * given incident.  It accepts an array of EventSummary objects and
 * formats each event with a human‑readable name and timestamp.  When
 * no events are available the component renders a simple placeholder.
 */

"use client";

import { type EventSummary } from "@/lib/api";

function friendlyEventType(t: string): string {
  return t
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
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

const MILESTONE_GROUPS = [
  { key: "collected", label: "Collected" },
  { key: "validated", label: "Validated" },
  { key: "exported", label: "Exported" },
  { key: "downloaded", label: "Downloaded" },
] as const;

function milestoneForEvent(eventType: string): (typeof MILESTONE_GROUPS)[number]["key"] {
  if (
    eventType.includes("hash") ||
    eventType.includes("validat") ||
    eventType.includes("integrity")
  ) {
    return "validated";
  }
  if (eventType.includes("export")) {
    return "exported";
  }
  if (eventType.includes("download")) {
    return "downloaded";
  }
  return "collected";
}

export default function Timeline({ events }: TimelineProps) {
  if (!events || events.length === 0) {
    return <p className="text-sm text-gray-400">No events yet.</p>;
  }

  const displayed = events.slice(-MAX_EVENTS);
  const grouped = new Map<
    (typeof MILESTONE_GROUPS)[number]["key"],
    EventSummary[]
  >();
  for (const event of displayed) {
    const key = milestoneForEvent(event.event_type);
    const bucket = grouped.get(key) ?? [];
    bucket.push(event);
    grouped.set(key, bucket);
  }

  return (
    <div className="space-y-5">
      {MILESTONE_GROUPS.map((group) => {
        const groupEvents = grouped.get(group.key) ?? [];
        return (
          <section key={group.key}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
              {group.label} ({groupEvents.length})
            </h3>
            {groupEvents.length === 0 ? (
              <p className="text-xs text-gray-400">No events.</p>
            ) : (
              <ol className="relative border-l border-gray-200 dark:border-gray-600">
                {groupEvents.map((ev, i) => (
                  <li key={`${group.key}-${i}`} className="mb-4 ml-4">
                    <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-blue-500 dark:border-gray-800" />
                    <time className="mb-1 text-xs text-gray-400">
                      {formatTime(ev.occurred_at_utc)}
                    </time>
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                      {friendlyEventType(ev.event_type)}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        );
      })}
    </div>
  );
}
