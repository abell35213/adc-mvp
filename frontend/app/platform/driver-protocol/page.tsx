import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Driver Protocol | ADC Platform",
  "Guide drivers through incident capture, coaching prompts, and completion workflows.",
  "/platform/driver-protocol",
);

export default function DriverProtocolPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Driver Protocol</h1>
      <p className="max-w-3xl text-slate-700">
        Standardize driver response with guided mobile flows that improve completion rates and evidence quality.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {[
          "Step-by-step incident capture with required fields",
          "Coaching prompts that reduce reporting gaps",
          "Supervisor visibility into adherence and completion",
          "Mobile-first flow designed for rapid roadside use",
        ].map((item) => (
          <article key={item} className="rounded-lg border border-slate-200 p-4">{item}</article>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/company/contact" label="See Driver Protocol flow" location="driver-protocol-primary" />
        <TrackedCta
          href="/company/contact"
          label="View driver experience"
          location="driver-protocol-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
