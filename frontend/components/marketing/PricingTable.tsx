import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const tiers = [
  { name: "Starter", price: "$299", features: ["Up to 25 vehicles", "Incident timeline", "CSV exports"] },
  { name: "Growth", price: "$799", features: ["Up to 150 vehicles", "Automated alerts", "PDF evidence bundles"] },
  { name: "Enterprise", price: "Contact", features: ["Unlimited vehicles", "Dedicated support", "Advanced retention controls"] },
];

export function PricingTable() {
  return (
    <MarketingSection id="pricing">
      <div className="space-y-4 text-center">
        <h2 className={marketingTokens.headingScale.h2}>Simple pricing for fleet scale.</h2>
        <p className="text-slate-700">All plans include secure evidence storage and role-based access controls.</p>
      </div>
      <div className="mt-10 grid gap-5 lg:grid-cols-3" role="list" aria-label="Pricing plans">
        {tiers.map((tier) => (
          <article key={tier.name} className={marketingTokens.surfaces.card} role="listitem">
            <h3 className={marketingTokens.headingScale.h3}>{tier.name}</h3>
            <p className="mt-3 text-3xl font-semibold text-slate-900">{tier.price}<span className="text-sm font-normal text-slate-600">/month</span></p>
            <ul className="mt-4 space-y-2 text-sm text-slate-700" role="list">
              {tier.features.map((feature) => <li key={feature}>• {feature}</li>)}
            </ul>
            <button className={`${marketingTokens.buttonVariants.primary} mt-6 w-full`} aria-label={`Choose ${tier.name} plan`}>
              Choose {tier.name}
            </button>
          </article>
        ))}
      </div>
    </MarketingSection>
  );
}
