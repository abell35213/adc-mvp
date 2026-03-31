import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Compliance Solution | ADC",
  "Automate compliance evidence collection and maintain audit-ready reporting across fleet operations.",
  "/solutions/compliance",
);

export default function CompliancePage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Compliance solution</h1>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Compliance Manager", "Monitor policy exceptions in one queue and route remediation with due dates."],
          ["Safety & Compliance Officer", "Export audit-ready artifacts with retention and access policies in place."],
          ["Operations Leadership", "Standardize compliance reporting to avoid operational slowdowns during audits."],
        ].map(([persona, copy]) => (
          <article key={persona} className="rounded-lg border border-slate-200 p-4">
            <h2 className="font-semibold">{persona}</h2>
            <p className="mt-2 text-sm text-slate-700">{copy}</p>
          </article>
        ))}
      </div>
      <TrackedCta href="/company/contact" label="Automate compliance" location="solutions-compliance" />
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
