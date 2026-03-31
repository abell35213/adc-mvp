import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Resources | ADC",
  "Browse fleet safety, claims defense, and compliance resources from ADC.",
  "/resources",
);

export default function ResourcesPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Resources</h1>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "Case studies with baseline vs. outcomes",
          "Operational playbooks for claims and compliance",
          "Implementation guides for safety and risk teams",
        ].map((resource) => (
          <article key={resource} className="rounded-lg border border-slate-200 p-4">
            {resource}
          </article>
        ))}
      </div>
      <TrackedCta href="/resources" label="Browse resources" location="resources-primary" />
      <QAChecklist phase="Phase 4" />
    </main>
  );
}
