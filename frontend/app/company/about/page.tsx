import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "About ADC",
  "Meet ADC leadership and milestones in fleet incident and claims technology.",
  "/company/about",
);

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-4 px-6 py-12">
      <h1 className="text-3xl font-bold">About ADC</h1>
      <p className="text-slate-700">We build practical tools for safer fleets and stronger claims outcomes.</p>
      <TrackedCta href="/company/careers" label="Meet the team" location="company-about-primary" />
    </main>
  );
}
