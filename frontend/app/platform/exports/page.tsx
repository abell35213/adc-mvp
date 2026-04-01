import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Exports | ADC Platform",
  "Generate compliant export packets for insurers, legal teams, and compliance reviewers.",
  "/platform/exports",
);

export default function PlatformExportsPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Exports</h1>
      <p className="max-w-3xl text-slate-700">
        Build insurer-ready, legal-ready, and audit-ready packets with traceable export actions and standardized
        delivery formats.
      </p>
      <ul className="grid gap-4 md:grid-cols-2">
        {[
          "Supported packet formats for insurer, legal, and compliance workflows",
          "Action-level audit trails for each export request",
          "Configurable packet templates by workflow and audience",
          "Operational SLAs for turnaround and completion tracking",
        ].map((item) => (
          <li key={item} className="rounded-lg border border-slate-200 p-4">{item}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/company/contact" label="Generate compliant exports" location="platform-exports-primary" />
        <TrackedCta
          href="/exports"
          label="View export formats"
          location="platform-exports-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
