"use client";

import MainLayout from "@/components/MainLayout";
import { useEffect, useState } from "react";
import { listIncidents, type Incident } from "@/lib/api";

/**
 * Live timeline page.  This page is intended to display a
 * chronological stream of events across all incidents using
 * server‑sent events or WebSockets.  For now it shows a placeholder
 * message and the number of active incidents.  Future iterations
 * could subscribe to a streaming endpoint and render events as they
 * arrive.
 */
export default function TimelinePage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listIncidents()
      .then(setIncidents)
      .finally(() => setLoading(false));
  }, []);

  return (
    <MainLayout title="Live Timeline">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          Live Timeline
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Visualize a chronological stream of events across all incidents as they
          unfold in real time.  Streaming support will be added in a future
          release.
        </p>
      </div>
      {loading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          There are currently {incidents.length} incidents being tracked.
        </p>
      )}
      <div className="mt-6 rounded border border-dashed p-8 text-center text-gray-400 dark:border-gray-700">
        Real‑time event streaming is coming soon. Check back later!
      </div>
    </MainLayout>
  );
}