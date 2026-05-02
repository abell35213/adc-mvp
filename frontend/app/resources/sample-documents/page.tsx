import type { Metadata } from "next";
import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";
import { SAMPLE_DOCUMENTS } from "@/lib/sampleDocuments";
import { buildPageMetadata } from "../../marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "Sample Documents | ADC",
  "Preview and download sample documents ADC produces at every stage of an incident — executive brief, insurance form, and legal defense packet.",
  "/resources/sample-documents",
);

export default function SampleDocumentsPage() {
  return (
    <main className={marketingTokens.surfaces.page}>
      <MarketingSection>
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-sky-600">
            Resources / Sample Documents
          </p>
          <h1 className={marketingTokens.headingScale.h2}>
            See exactly what ADC delivers
          </h1>
          <p className="max-w-3xl text-base leading-7 text-slate-600">
            Preview the documents ADC produces from a single fictitious incident — from the
            initial executive brief sent within minutes, through a carrier-specific insurance
            form, to a litigation-grade defense packet. Every document is marked
            &ldquo;SAMPLE&rdquo; on every page.
          </p>
        </div>

        <div className="mt-10 space-y-10">
          {SAMPLE_DOCUMENTS.map((doc) => (
            <article
              key={doc.id}
              id={doc.id}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <header className="flex flex-col gap-2 border-b border-slate-100 pb-4">
                <h2 className="text-2xl font-bold text-[#062040]">{doc.title}</h2>
                <p className="text-sm text-slate-500">
                  <span className="font-semibold text-slate-700">For:</span> {doc.audience}
                  {" · "}
                  <span className="font-semibold text-slate-700">When:</span> {doc.whenProduced}
                </p>
                <p className="mt-1 text-base leading-7 text-slate-600">{doc.description}</p>
              </header>

              <div className="mt-5 overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
                <iframe
                  src={doc.pdfHref}
                  title={`Inline preview of ${doc.title}`}
                  className="block h-[640px] w-full border-0"
                />
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <a
                  href={doc.pdfHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={marketingTokens.buttonVariants.primary}
                  aria-label={`Open ${doc.title} sample PDF in a new tab`}
                >
                  Open in new tab
                </a>
                <a
                  href={doc.pdfHref}
                  download={doc.downloadFileName}
                  className={marketingTokens.buttonVariants.secondary}
                  aria-label={`Download ${doc.title} sample PDF`}
                >
                  Download PDF
                </a>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-10 max-w-3xl text-sm text-slate-500">
          These samples are generated from fictitious data for demonstration purposes only and
          do not represent any real incident, claim, or filing. Want to see your own data in
          this format?{" "}
          <Link href="/company/contact" className="font-semibold text-[#1B6EF3] hover:underline">
            Talk to sales
          </Link>
          .
        </p>
      </MarketingSection>
    </main>
  );
}
