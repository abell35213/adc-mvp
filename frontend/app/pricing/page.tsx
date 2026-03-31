import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Pricing | ADC",
  "Review ADC pricing tiers and compare implementation support, workflow automation, and evidence features.",
  "/pricing",
);

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Pricing and comparison</h1>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 font-semibold">Plan</th>
              <th className="px-4 py-3 font-semibold">Best for</th>
              <th className="px-4 py-3 font-semibold">Highlights</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-slate-200">
              <td className="px-4 py-3 font-medium">Starter</td>
              <td className="px-4 py-3">Regional fleets proving ROI</td>
              <td className="px-4 py-3">Incident intake, evidence storage, monthly exports</td>
            </tr>
            <tr className="border-t border-slate-200">
              <td className="px-4 py-3 font-medium">Growth</td>
              <td className="px-4 py-3">Multi-site teams scaling safety ops</td>
              <td className="px-4 py-3">Automation rules, legal packet workflows, SLA support</td>
            </tr>
            <tr className="border-t border-slate-200">
              <td className="px-4 py-3 font-medium">Enterprise</td>
              <td className="px-4 py-3">National fleets with strict governance</td>
              <td className="px-4 py-3">Advanced controls, custom retention, dedicated advisory</td>
            </tr>
          </tbody>
        </table>
      </div>
      <TrackedCta href="/company/contact" label="Request pricing" location="pricing-primary" />
      <QAChecklist phase="Phase 3" />
    </main>
  );
}
