import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Claims Defense Solution | ADC",
  "Defend claims with verifiable evidence workflows and faster insurer-ready packet generation.",
  "/solutions/claims-defense",
);

export default function ClaimsDefensePage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Claims defense solution</h1>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Claims Manager", "Get complete evidence timelines in hours, not days, to reduce open-claim cycle time."],
          ["Risk Manager", "Use chain-of-custody logs to challenge disputed narratives with confident documentation."],
          ["General Counsel", "Prepare litigation-ready exports with immutable records and tamper-evident handling."],
        ].map(([persona, copy]) => (
          <article key={persona} className="rounded-lg border border-slate-200 p-4">
            <h2 className="font-semibold">{persona}</h2>
            <p className="mt-2 text-sm text-slate-700">{copy}</p>
          </article>
        ))}
      </div>
      <TrackedCta href="/company/contact" label="Defend claims faster" location="solutions-claims-defense" />
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
