import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Documentation | ADC Resources",
  "Access ADC quickstarts, integration references, and implementation documentation.",
  "/resources/docs",
);

export default function DocsPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Documentation</h1>
      <p className="max-w-3xl text-slate-700">
        Implementation guides for admins, technical evaluators, and operations teams.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "Quickstart for incident intake and evidence workflows",
          "Integration references for telematics and claims systems",
          "Troubleshooting and operational runbooks",
        ].map((doc) => (
          <article key={doc} className="rounded-lg border border-slate-200 p-4">{doc}</article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/resources/docs" label="Open documentation" location="docs-primary" />
        <TrackedCta
          href="/company/contact"
          label="Contact support/sales engineer"
          location="docs-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
    </main>
  );
}
