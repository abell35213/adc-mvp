"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import MainLayout from "@/components/MainLayout";
import { listIncidents, type Incident } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

/**
 * Dashboard landing page. Presents a hero section describing the core value
 * proposition of the Accident Documentation & Compliance (ADC) platform and
 * summarizes key information for the current organization. A grid of cards
 * directs users to the main sections of the app: incidents, evidence,
 * exports, vehicles and a live timeline. The incident count is fetched from
 * the backend to give users immediate insight into their active caseload.
 */
export default function DashboardPage() {
  const { user } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listIncidents()
      .then(setIncidents)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Derive counts for cards. Future enhancements could include exports and vehicles counts.
  const incidentCount = incidents.length;

  return (
    <MainLayout title="Dashboard">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="absolute inset-0 -z-10 h-full w-full">
          {/* Background image is decorative; it conveys connectivity and safety without depicting real entities. */}
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
            with real‑time visibility into your operations.
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
        </div>
      </section>

      {/* Feature Cards */}
      <section className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {/* Incidents Card */}
        <div className="rounded-lg border bg-white p-6 shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Incidents
          </h3>
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
            View and manage all recorded incidents. Monitor evidence capture and
            export status in real time.
          </p>
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : (
            <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
              {incidentCount}
            </p>
          )}
          <Link
            href="/incidents"
            className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            Go to incidents →
          </Link>
        </div>

        {/* Evidence Card */}
        <div className="rounded-lg border bg-white p-6 shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Evidence
          </h3>
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
            Capture dashcam footage, telematics and manual uploads to
            build a comprehensive evidence inventory.
          </p>
          <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
            —
          </p>
          <Link
            href="/incidents"
            className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            Manage evidence →
          </Link>
        </div>

        {/* Exports Card */}
        <div className="rounded-lg border bg-white p-6 shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Exports
          </h3>
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
            Generate court‑ready evidence packages with chain of custody and
            integrity reports.
          </p>
          <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
            —
          </p>
          <Link
            href="/exports"
            className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            View exports →
          </Link>
        </div>

        {/* Vehicles Card (admin only) */}
        {user?.role === "admin" && (
          <div className="rounded-lg border bg-white p-6 shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
              Vehicles
            </h3>
            <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
              Manage your fleet and QR codes. Add, edit or remove vehicles
              and rotate QR tokens.
            </p>
            <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
              —
            </p>
            <Link
              href="/vehicles"
              className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              Manage vehicles →
            </Link>
          </div>
        )}

        {/* Live Timeline Card */}
        <div className="rounded-lg border bg-white p-6 shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-2 text-xl font-semibold text-gray-900 dark:text-white">
            Live Timeline
          </h3>
          <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
            Visualize a chronological stream of events across all incidents
            as they unfold in real time.
          </p>
          <p className="mb-2 text-3xl font-bold text-blue-600 dark:text-blue-400">
            —
          </p>
          <Link
            href="/timeline"
            className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
          >
            View timeline →
          </Link>
        </div>
      </section>
    </MainLayout>
  );
}