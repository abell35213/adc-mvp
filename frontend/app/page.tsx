import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "./marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "ADC | Fleet incident response and claims defense",
  "ADC helps safety and risk teams respond faster with verifiable evidence and compliance-ready workflows.",
  "/",
);

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl space-y-10 px-6 py-12">
      <section className="space-y-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Phase 1: Home</p>
        <h1 className="text-4xl font-bold">Reduce claim exposure with evidence-ready incident operations.</h1>
        <p className="max-w-3xl text-slate-700">
          ADC gives fleet safety, risk, and operations leaders one workflow for incident intake, evidence
          retention, and insurer-ready exports.
        </p>
        <div className="flex flex-wrap gap-3">
          <TrackedCta href="/company/contact" label="Book a demo" location="home-hero" />
          <TrackedCta
            href="/product"
            label="View platform"
            location="home-hero"
            className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          />
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-3">
        {[
          "34% faster evidence packet turnaround",
          "22% lower average claim payout in contested cases",
          "2.5x increase in coaching follow-through",
        ].map((proof) => (
          <div key={proof} className="rounded-lg border border-slate-200 p-4 font-medium">
            {proof}
          </div>
        ))}
      </section>
      <QAChecklist phase="Phase 1" />
    </main>
  );
}
