import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const features = [
  { icon: "🎥", title: "Unified incident timeline", body: "Merge video, ELD, GPS, and safety events into one chronological view." },
  { icon: "🔒", title: "Evidence integrity", body: "Track every file access with immutable chain-of-custody logs." },
  { icon: "📦", title: "Automated exports", body: "Generate insurer-ready incident packages in minutes, not hours." },
  { icon: "🔔", title: "Operational alerts", body: "Escalate high-risk events to the right people automatically." },
  { icon: "🤖", title: "AI risk scoring", body: "Every incident is scored for severity and litigation risk instantly." },
  { icon: "📊", title: "Fleet-wide analytics", body: "Spot coaching opportunities and behavior trends across your entire fleet." },
];

export function FeatureGrid() {
  return (
    <section id="features" className="bg-white border-t border-slate-200 py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10 text-center">
          <h2 className={marketingTokens.headingScale.h2}>Everything your safety desk needs to move fast.</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-600">
            Purpose-built workflows for response teams, adjusters, and compliance leaders.
          </p>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon, title, body }) => (
            <article key={title} className={marketingTokens.surfaces.card}>
              <span className="text-2xl" aria-hidden="true">{icon}</span>
              <h3 className="mt-3 text-base font-semibold text-slate-900">{title}</h3>
              <p className="mt-2 text-sm text-slate-600">{body}</p>
            </article>
          ))}
        </div>
      </MarketingContainer>
    </section>
  );
}
