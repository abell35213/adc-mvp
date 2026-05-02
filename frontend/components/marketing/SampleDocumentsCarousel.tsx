"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";
import { SAMPLE_DOCUMENTS } from "@/lib/sampleDocuments";
import { trackCtaClick } from "@/lib/tracking";

const ROTATE_INTERVAL_MS = 6000;

export function SampleDocumentsCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return undefined;
    const interval = setInterval(() => {
      setActiveIndex((current) => (current + 1) % SAMPLE_DOCUMENTS.length);
    }, ROTATE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isPaused]);

  const active = SAMPLE_DOCUMENTS[activeIndex];

  return (
    <MarketingSection id="sample-documents">
      <div className="space-y-3">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500" aria-hidden="true" />
          See it in action
        </span>
        <h2 className={marketingTokens.headingScale.h2}>What ADC delivers, end to end</h2>
        <p className={marketingTokens.headingScale.body}>
          From the first executive brief to the courtroom-ready defense packet — preview the documents
          ADC produces at every stage of an incident.
        </p>
      </div>

      <div
        className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.4fr]"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
        onFocus={() => setIsPaused(true)}
        onBlur={() => setIsPaused(false)}
      >
        {/* Tab list */}
        <div role="tablist" aria-label="Sample documents" className="flex flex-col gap-3">
          {SAMPLE_DOCUMENTS.map((doc, idx) => {
            const isActive = idx === activeIndex;
            return (
              <button
                key={doc.id}
                role="tab"
                type="button"
                id={`sample-tab-${doc.id}`}
                aria-selected={isActive}
                aria-controls={`sample-panel-${doc.id}`}
                tabIndex={isActive ? 0 : -1}
                onClick={() => setActiveIndex(idx)}
                className={`rounded-2xl border p-5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] ${
                  isActive
                    ? "border-[#1B6EF3] bg-white shadow-md"
                    : "border-slate-200 bg-white/60 hover:border-sky-300 hover:bg-white"
                }`}
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-600">
                  Document {idx + 1} of {SAMPLE_DOCUMENTS.length}
                </p>
                <h3 className="mt-1 text-lg font-semibold text-[#062040]">{doc.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{doc.whenProduced}</p>
                <p className="mt-1 text-xs text-slate-500">For {doc.audience}</p>
              </button>
            );
          })}
        </div>

        {/* Active panel */}
        <div
          role="tabpanel"
          id={`sample-panel-${active.id}`}
          aria-labelledby={`sample-tab-${active.id}`}
          className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-bold text-[#062040]">{active.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{active.description}</p>
            </div>
          </div>

          <div className="mt-5 overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
            {/*
              Inline PDF preview using <object> with an <iframe> fallback.
              The PDF is a static asset under /public/samples; browsers render it
              with their built-in viewer.
            */}
            <object
              key={active.id}
              data={`${active.pdfHref}#toolbar=0&navpanes=0`}
              type="application/pdf"
              aria-label={`Inline preview of ${active.title}`}
              className="block h-[420px] w-full"
            >
              <iframe
                src={active.pdfHref}
                title={`Inline preview of ${active.title}`}
                className="block h-[420px] w-full border-0"
              />
            </object>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <a
              href={active.pdfHref}
              target="_blank"
              rel="noopener noreferrer"
              className={marketingTokens.buttonVariants.primary}
              aria-label={`Open ${active.title} sample PDF in a new tab`}
              data-track-event="marketing_cta_click"
              data-track-location="home-sample-carousel-open"
              data-track-label={active.shortTitle}
              onClick={() =>
                trackCtaClick({
                  event: "marketing_cta_click",
                  location: "home-sample-carousel-open",
                  label: active.shortTitle,
                })
              }
            >
              Open in new tab
            </a>
            <a
              href={active.pdfHref}
              download={active.downloadFileName}
              className={marketingTokens.buttonVariants.secondary}
              aria-label={`Download ${active.title} sample PDF`}
              data-track-event="marketing_cta_click"
              data-track-location="home-sample-carousel-download"
              data-track-label={active.shortTitle}
              onClick={() =>
                trackCtaClick({
                  event: "marketing_cta_click",
                  location: "home-sample-carousel-download",
                  label: active.shortTitle,
                })
              }
            >
              Download PDF
            </a>
            <Link
              href="/resources/sample-documents"
              className={marketingTokens.buttonVariants.ghost}
            >
              See all sample documents →
            </Link>
          </div>

          <p className="mt-4 text-xs text-slate-500">
            All previews are generated from fictitious sample data and watermarked
            &ldquo;SAMPLE&rdquo; on every page.
          </p>
        </div>
      </div>
    </MarketingSection>
  );
}
