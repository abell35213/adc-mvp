import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const customers = [
  {
    name: "NorthLine Freight",
    initial: "NF",
    color: "text-red-600",
    metric: "50%",
    label: "Reduction in claim cycle time",
    href: "/resources",
  },
  {
    name: "PacWest Logistics",
    initial: "PW",
    color: "text-amber-600",
    metric: "$2.1M",
    label: "Saved in claim payouts annually",
    href: "/resources",
  },
  {
    name: "Sterling Transport",
    initial: "ST",
    color: "text-sky-700",
    metric: "8,000+",
    label: "Investigator hours saved",
    href: "/resources",
  },
  {
    name: "Summit Energy Fleet",
    initial: "SE",
    color: "text-green-600",
    metric: "28%",
    label: "Improvement in vehicle utilization",
    href: "/resources",
  },
  {
    name: "CrossCountry Carriers",
    initial: "CC",
    color: "text-purple-600",
    metric: "5-year",
    label: "Low DOT reportable accident streak",
    href: "/resources",
  },
  {
    name: "City Metro Transit",
    initial: "CM",
    color: "text-slate-700",
    metric: "81%",
    label: "Reduction in collision risk within 6 months",
    href: "/resources",
  },
];

export function CustomerResults() {
  return (
    <section className="bg-slate-50 border-t border-slate-200 py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10 text-center">
          <span className={marketingTokens.badge}>
            <span className="h-1.5 w-1.5 rounded-full bg-sky-600" />
            Customer Stories
          </span>
          <h2 className={`${marketingTokens.headingScale.h2} mt-4`}>Results our customers love.</h2>
          <p className={`${marketingTokens.headingScale.body} mx-auto mt-3 max-w-2xl`}>
            From mid-market fleets to enterprise carriers, ADC delivers measurable outcomes.
          </p>
        </div>

        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" role="list" aria-label="Customer results">
          {customers.map((c) => (
            <li key={c.name} className={marketingTokens.surfaces.card}>
              {/* Logo placeholder */}
              <div className="mb-4 h-8 flex items-center">
                <span className={`text-lg font-bold tracking-tight ${c.color}`}>{c.name}</span>
              </div>
              <p className="text-3xl font-bold text-slate-900">{c.metric}</p>
              <div className="mt-3 flex items-center justify-between gap-2">
                <p className="text-sm text-slate-600">{c.label}</p>
                <Link
                  href={c.href}
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white transition hover:bg-sky-600"
                  aria-label={`Read ${c.name} case study`}
                >
                  →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </MarketingContainer>
    </section>
  );
}
