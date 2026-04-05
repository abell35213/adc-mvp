import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Evidence Vault | ADC Platform",
  "Manage immutable evidence with retention controls, access logs, and legal-ready artifact packaging.",
  "/platform/evidence-vault",
);

export default function EvidenceVaultPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-12">
      <h1 className="text-3xl font-bold">Evidence Vault</h1>
      <p className="max-w-3xl text-slate-700">
        Preserve chain-of-custody from intake to export with tamper-evident storage and policy-driven retention.
      </p>
      <ul className="grid gap-4 md:grid-cols-2">
        {[
          "Immutable evidence handling and event-level audit logs",
          "Retention policy controls by incident type and jurisdiction",
          "Role-based review workflow for claims, legal, and compliance",
          "Previewable artifact bundles before export generation",
        ].map((proof) => (
          <li key={proof} className="rounded-lg border border-slate-200 p-4">{proof}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-3">
        <TrackedCta href="/company/contact" label="See Evidence Vault demo" location="evidence-vault-primary" />
        <TrackedCta
          href="/platform/exports"
          label="Download sample export"
          location="evidence-vault-secondary"
          className="inline-flex rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        />
      </div>
      <QAChecklist phase="Phase 2" />
    </main>
  );
}
