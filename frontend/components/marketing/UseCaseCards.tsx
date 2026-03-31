import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const pillars = [
  {
    title: "Safety",
    subtitle: "Use AI to predict and prevent risks inside and outside the cab.",
    features: [
      "30+ risk detection categories",
      "Weather-hazard and road-condition alerts",
      "Real-time coaching, training & recognition",
      "Worker safety in the cab and on site",
    ],
    href: "/solutions",
  },
  {
    title: "Efficiency",
    subtitle: "Reduce costs, maximize utilization, and streamline workflows.",
    features: [
      "Automated incident intake",
      "Route and dispatch optimization",
      "Fuel and idling insights",
      "Improved fleet and asset utilization",
    ],
    href: "/solutions",
  },
  {
    title: "Reliability",
    subtitle: "Enterprise security, unmatched connectivity, and premier support.",
    features: [
      "99.9% platform uptime",
      "Lifetime evidence warranty",
      "24/7 support and onboarding",
    ],
    href: "/solutions",
  },
];

export function UseCaseCards() {
  return (
    <section className="bg-[#0a1628] py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10">
          <span className={marketingTokens.badgeLight}>
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
            Why ADC?
          </span>
          <h2 className={`${marketingTokens.headingScale.h2Light} mt-4 max-w-2xl`}>
            Trusted by teams who keep operations moving.
          </h2>
          <p className="mt-3 max-w-xl text-slate-300">
            We help fleet organizations improve safety, efficiency, and reliability with AI-powered
            technology built for the field.
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          {pillars.map((pillar) => (
            <article key={pillar.title} className={`${marketingTokens.surfaces.cardNavy} flex flex-col`}>
              <h3 className="text-xl font-semibold text-white">{pillar.title}</h3>
              <p className="mt-2 text-sm text-slate-300">{pillar.subtitle}</p>
              <ul className="mt-5 flex-1 space-y-2.5" aria-label={`${pillar.title} features`}>
                {pillar.features.map((feat) => (
                  <li key={feat} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" aria-hidden="true">✓</span>
                    {feat}
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                <Link href={pillar.href} className={marketingTokens.buttonVariants.primaryLight} aria-label={`Learn more about ${pillar.title}`}>
                  Learn more
                </Link>
              </div>
            </article>
          ))}
        </div>
      </MarketingContainer>
    </section>
  );
}
