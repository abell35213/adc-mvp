import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const tiers = [
  { name: "Starter", price: "$299", features: ["Up to 25 vehicles", "Incident timeline", "CSV exports"], highlight: false },
  { name: "Growth", price: "$799", features: ["Up to 150 vehicles", "Automated alerts", "PDF evidence bundles"], highlight: true },
  { name: "Enterprise", price: "Contact us", features: ["Unlimited vehicles", "Dedicated support", "Advanced retention controls"], highlight: false },
];

export function PricingTable() {
  return (
    <section id="pricing" className="bg-slate-50 border-t border-slate-200 py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10 text-center">
          <h2 className={marketingTokens.headingScale.h2}>Simple pricing for fleet scale.</h2>
          <p className="mt-3 text-slate-600">All plans include secure evidence storage and role-based access controls.</p>
        </div>
        <div className="grid gap-5 lg:grid-cols-3" role="list" aria-label="Pricing plans">
          {tiers.map((tier) => (
            <article
              key={tier.name}
              className={tier.highlight ? "rounded-2xl border-2 border-sky-600 bg-white p-6 shadow-md" : marketingTokens.surfaces.card}
              role="listitem"
            >
              {tier.highlight && (
                <span className="mb-3 inline-flex rounded-full bg-sky-600 px-3 py-0.5 text-xs font-semibold text-white">Most popular</span>
              )}
              <h3 className="text-xl font-semibold text-slate-900">{tier.name}</h3>
              <p className="mt-3 text-3xl font-bold text-slate-900">
                {tier.price}
                {tier.price !== "Contact us" && <span className="text-sm font-normal text-slate-500">/mo</span>}
              </p>
              <ul className="mt-5 space-y-2 text-sm text-slate-600" role="list">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <span className="text-sky-500" aria-hidden="true">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
                <Link
                  href="/company/contact"
                  className={`${tier.highlight ? marketingTokens.buttonVariants.primary : marketingTokens.buttonVariants.secondary} mt-6 w-full`}
                  aria-label={`Choose ${tier.name} plan`}
                >
                  {tier.name === "Enterprise" ? "Contact sales" : "Get started"}
                </Link>
            </article>
          ))}
        </div>
      </MarketingContainer>
    </section>
  );
}
