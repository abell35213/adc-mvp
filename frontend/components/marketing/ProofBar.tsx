import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const stats = [
  { value: "8×", label: "ROI", sub: "On average when reviewing savings on fuel, maintenance, and insurance." },
  { value: "34%", label: "Faster evidence turnaround", sub: "Incident packets ready before adjusters ask." },
  { value: "22%", label: "Lower average claim payout", sub: "In contested cases using ADC evidence exports." },
  { value: "#1", label: "Trusted platform", sub: "Most trusted fleet evidence platform for mid-market fleets." },
];

export function ProofBar() {
  return (
    <section className="bg-slate-50 border-y border-slate-200 py-14 sm:py-18">
      <MarketingContainer>
        <div className="text-center mb-10">
          <span className={marketingTokens.badge}>
            <span className="h-1.5 w-1.5 rounded-full bg-sky-600" />
            Proven Results
          </span>
          <h2 className={`${marketingTokens.headingScale.h2} mt-4`}>Proven value. Real results.</h2>
        </div>
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4" aria-label="Key performance metrics">
          {stats.map((stat) => (
            <li key={stat.value} className={marketingTokens.surfaces.card}>
              <p className="text-4xl font-bold text-slate-900">{stat.value}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{stat.label}</p>
              <p className="mt-2 text-sm text-slate-600">{stat.sub}</p>
            </li>
          ))}
        </ul>
      </MarketingContainer>
    </section>
  );
}
