import { Suspense } from "react";
import DashboardClient from "./DashboardClient";

export default function DashboardPage() {
  // DashboardClient uses useSearchParams() which requires a Suspense
  // boundary during static prerender.
  return (
    <Suspense fallback={<div className="min-h-screen bg-page p-6 text-text-muted">Loading command center…</div>}>
      <DashboardClient />
    </Suspense>
  );
}
