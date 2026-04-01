import type { Metadata } from "next";
import { buildPageMetadata } from "../marketingSeo";

const effectiveDate = "April 1, 2026";

export const metadata: Metadata = buildPageMetadata(
  "Privacy Policy | ADC",
  "Understand what data ADC collects, how it is used, retention practices, and how to submit privacy requests.",
  "/privacy",
);

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-12 text-slate-800">
      <h1 className="text-3xl font-bold">Privacy Policy</h1>
      <p className="text-sm text-slate-500">Effective date: {effectiveDate}</p>
      <p>
        ADC collects account, operational, and incident-response data to deliver platform services, improve product
        reliability, and support customer reporting requirements.
      </p>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">What we collect</h2>
        <ul className="list-disc space-y-1 pl-6">
          <li>Account and profile information submitted by customers and authorized users.</li>
          <li>Incident artifacts, supporting evidence, and workflow activity records.</li>
          <li>Usage telemetry used for performance, security, and troubleshooting.</li>
        </ul>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Retention and controls</h2>
        <p>
          Data retention aligns with customer-configured policies, regulatory requirements, and contractual obligations.
          Audit trails are maintained for key evidence and export actions.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Privacy requests</h2>
        <p>
          Submit privacy questions or rights requests through <a className="underline" href="/company/contact">our contact page</a> and
          include the phrase &quot;Privacy Request&quot; for routing.
        </p>
      </section>
    </main>
  );
}
