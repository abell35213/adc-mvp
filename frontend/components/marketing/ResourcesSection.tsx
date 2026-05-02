import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const featured = {
  type: "Sample document",
  title: "From collision alert to counsel-ready file: see ADC's documents end-to-end",
  summary:
    "Preview the executive brief, insurance form, and legal defense packet ADC produces from a single incident — all generated from fictitious sample data and watermarked SAMPLE.",
  href: "/resources/sample-documents",
  cta: "Browse sample documents →",
};

const reports = [
  {
    type: "Sample document",
    title: "Sample: Initial Executive Brief sent within minutes of an incident",
    href: "/resources/sample-documents#executive-brief",
    cta: "Preview executive brief →",
  },
  {
    type: "Sample document",
    title: "Sample: insurer-ready FNOL form pre-filled from incident data",
    href: "/resources/sample-documents#insurance-form",
    cta: "Preview insurance form →",
  },
  {
    type: "Sample document",
    title: "Sample: court-ready legal defense packet with chain-of-custody",
    href: "/resources/sample-documents#legal-defense-packet",
    cta: "Preview defense packet →",
  },
];

export function ResourcesSection() {
  return (
    <MarketingSection>
      <div className="space-y-3">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500" aria-hidden="true" />
          Resources
        </span>
        <h2 className={marketingTokens.headingScale.h2}>
          Proof resources for risk, legal, and claims teams
        </h2>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        {/* Featured report */}
        <article className="flex flex-col rounded-2xl bg-slate-800 p-8 text-white">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-sky-400">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" aria-hidden="true" />
            {featured.type}
          </p>
          <div className="my-6 flex-1 rounded-xl bg-slate-700/60 flex items-center justify-center overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/hero.png"
              alt="ADC Safety Report cover"
              className="h-full w-full object-cover rounded-xl opacity-80"
            />
          </div>
          <h3 className="text-lg font-semibold leading-snug">{featured.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">{featured.summary}</p>
          <Link
            href={featured.href}
            className="mt-5 inline-flex items-center text-sm font-semibold text-sky-400 hover:text-sky-300"
            aria-label={`Read: ${featured.title}`}
          >
            {featured.cta}
          </Link>
        </article>

        {/* Report list */}
        <div className="flex flex-col divide-y divide-slate-100">
          {reports.map(({ type, title, href, cta }) => (
            <article key={title} className="flex items-start gap-4 py-5 first:pt-0 last:pb-0">
              <div className="h-16 w-16 shrink-0 rounded-lg bg-slate-100 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/hero.png"
                  alt={`Thumbnail for: ${title}`}
                  className="h-full w-full object-cover"
                />
              </div>
              <div className="flex-1 space-y-1">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-sky-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-500" aria-hidden="true" />
                  {type}
                </p>
                <h3 className="text-sm font-semibold leading-snug text-slate-900">{title}</h3>
                <Link
                  href={href}
                  className="inline-flex items-center text-xs font-semibold text-sky-600 hover:text-sky-500"
                  aria-label={`Read: ${title}`}
                >
                  {cta}
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </MarketingSection>
  );
}
