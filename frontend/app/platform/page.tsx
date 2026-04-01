import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Platform | ADC",
  "Explore ADC platform architecture, module map, role-based controls, and integration surface.",
  "/platform",
);

export default function PlatformPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Platform</h1>
      <p className="max-w-3xl text-slate-700">
        ADC unifies incident intake, evidence control, driver workflows, and legal-ready exports in a single
        role-based platform.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {[
          "Modular workflows for safety, claims, and compliance teams",
          "Role-based access with immutable audit trails",
          "APIs and integrations for telematics, claims, and documentation systems",
          "Security and reliability guardrails for high-trust operations",
        ].map((item) => (
          <article key={item} className="rounded-lg border border-slate-200 p-4">
            {item}
          </article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/platform" label="Explore platform" location="platform-primary" />
        <TrackedCta
          href="/product"
          label="See all features"
          location="platform-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
