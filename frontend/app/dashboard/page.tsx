import { Suspense } from "react";
import DashboardClient from "./DashboardClient";

export default function DashboardPage() {
  // DashboardClient uses useSearchParams() which requires a Suspense
  // boundary during static prerender.
  return (
    <Suspense fallback={null}>
      <DashboardClient />
    </Suspense>
  );
}
