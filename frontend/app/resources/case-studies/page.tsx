import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Case Studies | ADC Resources",
  "Read outcomes-focused case studies from fleet safety, claims, and compliance teams using ADC.",
  "/resources/case-studies",
);

export default function CaseStudiesPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Case studies</h1>
      <p className="max-w-3xl text-slate-700">
        Peer examples showing baseline challenges, deployment approach, and measurable outcomes.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "Regional carrier: 32% faster evidence turnaround",
          "National fleet: 18% reduction in preventable incidents",
          "Mixed-asset operator: 26% faster claims closure",
        ].map((study) => (
          <article key={study} className="rounded-lg border border-slate-200 p-4">{study}</article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/resources/case-studies" label="Read case study" location="case-studies-primary" />
        <TrackedCta
          href="/company/contact"
          label="Book a similar assessment"
          location="case-studies-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
    </main>
  );
}
