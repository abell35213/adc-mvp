import type { Metadata } from "next";
import { buildPageMetadata } from "../marketingSeo";

const effectiveDate = "April 1, 2026";

export const metadata: Metadata = buildPageMetadata(
  "Terms of Service | ADC",
  "Review ADC service terms, acceptable use requirements, termination terms, and legal contact details.",
  "/terms",
);

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-12 text-slate-800">
      <h1 className="text-3xl font-bold">Terms of Service</h1>
      <p className="text-sm text-slate-500">Effective date: {effectiveDate}</p>
      <p>
        These Terms govern access to and use of ADC services by customer organizations and authorized users.
      </p>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Service scope</h2>
        <p>
          ADC provides hosted software for incident documentation, evidence workflows, and export operations as
          described in applicable order forms.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Acceptable use</h2>
        <p>
          Users must follow applicable law, protect account credentials, and avoid misuse that disrupts system
          integrity, security, or availability.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Termination and legal contact</h2>
        <p>
          Termination rights, liability boundaries, and governing law are defined in customer agreements. For legal
          inquiries, use <a className="underline" href="/company/contact">the contact page</a> and include the phrase &quot;Legal Request&quot;.
        </p>
      </section>
    </main>
  );
}
