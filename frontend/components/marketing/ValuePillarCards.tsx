import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const pillars = [
  {
    title: "Safety",
    tagline: "Use AI to predict and prevent risks inside and outside the cab.",
    bullets: [
      "30+ risk detection models",
      "Weather-hazard alerts",
      "Real-time coaching, training & recognition",
      "Worker safety in the cab and on site",
    ],
    href: "/solutions/fleet-safety",
  },
  {
    title: "Efficiency",
    tagline: "Reduce costs, maximize utilization, and streamline workflows.",
    bullets: [
      "Predictive maintenance",
      "Route optimization",
      "Fuel and idling insights",
      "Improved fleet and asset utilization",
    ],
    href: "/solutions",
  },
  {
    title: "Reliability",
    tagline: "Enterprise security, unmatched connectivity, and premier support.",
    bullets: [
      "99.99% uptime",
      "Lifetime hardware warranty",
      "24/7 support",
    ],
    href: "/solutions/compliance",
  },
];

export function ValuePillarCards() {
  return (
    <MarketingSection>
      <div className="space-y-3 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500" aria-hidden="true" />
          Why ADC?
        </span>
        <h2 className={`${marketingTokens.headingScale.h2} mx-auto max-w-2xl`}>
          Trusted by teams who keep operations moving
        </h2>
        <p className="mx-auto max-w-2xl text-slate-600">
          We help organizations improve safety, efficiency, and reliability with AI-powered
          technology built for the field.
        </p>
      </div>

      <div className="mt-10 grid gap-5 lg:grid-cols-3">
        {pillars.map((pillar) => (
          <article
            key={pillar.title}
            className="flex flex-col rounded-2xl bg-slate-800 p-7 text-white"
          >
            <h3 className="text-xl font-semibold">{pillar.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">{pillar.tagline}</p>
            <ul className="mt-6 flex-1 space-y-3 text-sm text-slate-200">
              {pillar.bullets.map((bullet) => (
                <li key={bullet} className="flex items-start gap-2">
                  <span className="mt-0.5 h-4 w-4 shrink-0 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center text-[10px]">
                    ✓
                  </span>
                  {bullet}
                </li>
              ))}
            </ul>
            <Link
              href={pillar.href}
              className="mt-8 inline-flex w-full items-center justify-center rounded-md bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
            >
              Learn more
            </Link>
          </article>
        ))}
      </div>
    </MarketingSection>
  );
}
