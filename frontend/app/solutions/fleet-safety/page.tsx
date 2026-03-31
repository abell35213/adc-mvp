import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Fleet Safety Solution | ADC",
  "Help safety leaders reduce incident rates with guided coaching and driver protocol automation.",
  "/solutions/fleet-safety",
);

export default function FleetSafetyPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Fleet safety solution</h1>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Safety Director", "Track leading indicators and reduce preventable incidents with weekly action plans."],
          ["Fleet Safety Manager", "Launch consistent coaching loops with templated follow-up and completion reporting."],
          ["Operations Executive", "Balance uptime and risk with lane-level visibility into driver behavior trends."],
        ].map(([persona, copy]) => (
          <article key={persona} className="rounded-lg border border-slate-200 p-4">
            <h2 className="font-semibold">{persona}</h2>
            <p className="mt-2 text-sm text-slate-700">{copy}</p>
          </article>
        ))}
      </div>
      <TrackedCta href="/company/contact" label="Improve driver safety" location="solutions-fleet-safety" />
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
