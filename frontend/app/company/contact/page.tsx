import type { Metadata } from "next";
import LeadForm from "@/components/marketing/LeadForm";
import QAChecklist from "@/components/marketing/QAChecklist";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Contact ADC",
  "Get in touch with ADC sales, support, and partnership teams.",
  "/company/contact",
);

export default function ContactPage() {
  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-6 py-12 md:grid-cols-2">
      <section>
        <h1 className="text-3xl font-bold">Contact ADC</h1>
        <p className="mt-3 text-slate-700">
          Share your fleet size and goals. We route messages to sales, support, or partnerships and respond within
          one business day.
        </p>
        <p className="mt-2 text-sm text-slate-500">By submitting, you agree to ADC contact and privacy practices.</p>
      </section>
      <section className="space-y-4">
        <LeadForm />
        <QAChecklist phase="Phase 1" />
      </section>
    </main>
  );
}
