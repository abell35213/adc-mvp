import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Company | ADC",
  "Learn about ADC mission, team, and company updates for fleet incident operations.",
  "/company",
);

export default function CompanyPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-12">
      <h1 className="text-3xl font-bold">Company</h1>
      <p className="text-slate-700">ADC helps fleets document incidents with confidence and operational speed.</p>
      <TrackedCta href="/company/contact" label="About ADC" location="company-primary" />
      <QAChecklist phase="Phase 4" />
    </main>
  );
}
