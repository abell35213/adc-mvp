import type { Metadata } from "next";
import TrackedCta from "@/components/marketing/TrackedCta";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "ADC Careers",
  "View open roles and learn about the ADC hiring process and culture.",
  "/company/careers",
);

export default function CareersPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-4 px-6 py-12">
      <h1 className="text-3xl font-bold">Careers</h1>
      <p className="text-slate-700">We are hiring across product, engineering, and fleet operations advisory.</p>
      <TrackedCta href="/company/contact" label="View open roles" location="company-careers-primary" />
    </main>
  );
}
