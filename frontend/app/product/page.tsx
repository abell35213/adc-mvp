import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "ADC Product Overview",
  "Understand ADC workflows for incident response, chain of custody, and legal-ready exports.",
  "/product",
);

export default function ProductPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Product overview</h1>
      <p className="max-w-3xl text-slate-700">
        Map incidents from first notice of loss through claims resolution with integrated evidence, audit trails,
        and insurer-ready exports.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "Incident intake and triage automation",
          "Immutable evidence vault with role-based access",
          "One-click export packets for insurers and counsel",
        ].map((item) => (
          <div key={item} className="rounded-lg border border-slate-200 p-4">{item}</div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/company/contact" label="Start product tour" location="product-primary" />
        <TrackedCta
          href="/company/contact"
          label="Talk to sales"
          location="product-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
      <QAChecklist phase="Phase 1" />
    </main>
  );
}
