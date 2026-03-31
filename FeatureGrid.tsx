import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const features = [
  ["Unified timeline", "Merge video, ELD, GPS, and safety events by incident."],
  ["Evidence integrity", "Track each file access with immutable chain-of-custody logs."],
  ["Automated exports", "Generate insurer-ready incident packages in minutes."],
  ["Operational alerts", "Escalate high-risk events to the right people automatically."],
];

export function FeatureGrid() {
  return (
    <MarketingSection id="features">
      <div className="space-y-4 text-center">
        <h2 className={marketingTokens.headingScale.h2}>Everything your safety desk needs to move fast.</h2>
        <p className="mx-auto max-w-3xl text-slate-700">Purpose-built workflows for response teams, adjusters, and compliance leaders.</p>
      </div>
      <div className="mt-10 grid gap-5 md:grid-cols-2">
        {features.map(([title, body]) => (
          <article key={title} className={marketingTokens.surfaces.card}>
            <h3 className={marketingTokens.headingScale.h3}>{title}</h3>
            <p className="mt-3 text-slate-700">{body}</p>
          </article>
        ))}
      </div>
    </MarketingSection>
  );
}
