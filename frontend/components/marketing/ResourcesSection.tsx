import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const featured = {
  type: "Report",
  title: "ADC AI helps reduce crash rates by nearly 75%",
  body: "Based on 10,000+ fleet incidents, the ADC Safety Report reveals how AI-powered evidence collection improves crash rates, risky behaviors, and claim outcomes.",
  href: "/resources",
  imageBg: "bg-sky-900",
};

const reports = [
  {
    type: "Report",
    title: "ADC rated No. 1: Satisfaction, support & service",
    href: "/resources",
    imageBg: "bg-slate-700",
  },
  {
    type: "Report",
    title: "Plan, act, recover: Tech is reshaping incident preparedness",
    href: "/resources",
    imageBg: "bg-slate-600",
  },
  {
    type: "Report",
    title: "IDC study: ADC delivers 8× ROI for fleet operations",
    href: "/resources",
    download: true,
    imageBg: "bg-sky-700",
  },
];

export function ResourcesSection() {
  return (
    <section className="bg-white border-t border-slate-200 py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10">
          <span className={marketingTokens.badge}>
            <span className="h-1.5 w-1.5 rounded-full bg-sky-600" />
            Resources
          </span>
          <h2 className={`${marketingTokens.headingScale.h2} mt-4`}>Keep up with our latest news and updates.</h2>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          {/* Featured report */}
          <article className="flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className={`${featured.imageBg} flex h-52 items-center justify-center`}>
              <div className="rounded-xl border border-white/20 bg-white/10 p-6 text-center">
                <p className="text-sm font-bold text-white">ADC Safety Report</p>
                <p className="mt-1 text-xs text-sky-200">2024 Edition</p>
              </div>
            </div>
            <div className="flex flex-1 flex-col p-6">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                {featured.type}
              </span>
              <h3 className="mt-2 text-lg font-semibold text-slate-900">{featured.title}</h3>
              <p className="mt-2 flex-1 text-sm text-slate-600">{featured.body}</p>
              <Link
                href={featured.href}
                className={`${marketingTokens.buttonVariants.ghost} mt-5`}
                aria-label={`Read the report: ${featured.title}`}
              >
                See the report →
              </Link>
            </div>
          </article>

          {/* Side reports */}
          <div className="flex flex-col gap-5">
            {reports.map((report) => (
              <article key={report.title} className="flex items-start gap-4 rounded-xl border border-slate-200 bg-white p-4">
                <div className={`${report.imageBg} h-16 w-20 shrink-0 rounded-lg`} aria-hidden="true" />
                <div className="flex-1 min-w-0">
                  <span className="flex items-center gap-1 text-xs font-semibold text-slate-500">
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                    {report.type}
                  </span>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{report.title}</p>
                  <Link
                    href={report.href}
                    className={`${marketingTokens.buttonVariants.ghost} mt-2`}
                    aria-label={`${report.download ? "Download" : "See"} the report: ${report.title}`}
                  >
                    {report.download ? "Download the report ↓" : "See the report →"}
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </MarketingContainer>
    </section>
  );
}
