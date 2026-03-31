import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function AIInsightsSection() {
  return (
    <section className="bg-[#0a1628] border-t border-white/10 py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="mb-10">
          <span className={marketingTokens.badgeLight}>
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
            AI-Driven Insights
          </span>
          <h2 className={`${marketingTokens.headingScale.h2Light} mt-4 max-w-3xl`}>
            Let the intelligence of thousands of fleets improve your operations.
          </h2>
          <p className="mt-4 max-w-2xl text-slate-300">
            Using data from tens of thousands of incidents, ADC&apos;s AI surfaces patterns and risk
            signals so your safety team can act before a claim becomes a liability.
          </p>
        </div>

        {/* Mockup area */}
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0f2040]">
          <div className="grid lg:grid-cols-2">
            {/* Left: phone mockup */}
            <div className="flex items-center justify-center p-8 sm:p-12">
              <div className="w-full max-w-xs rounded-3xl border border-white/20 bg-[#0a1628] p-4 shadow-2xl">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-semibold text-white">9:41</span>
                  <span className="text-xs text-slate-400">ADC Evidence App</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-[#0f2040] p-4">
                  <p className="text-xs font-semibold text-white mb-1">Incident Report</p>
                  <p className="text-xs text-slate-400 mb-3">Trailer Capture — AI Autofill</p>
                  <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 mb-3">
                    <p className="text-xs font-medium text-sky-300">* Required</p>
                    <p className="text-xs text-white mt-0.5">Dash Camera Footage</p>
                    <p className="text-xs text-slate-400 mt-0.5">Add a clip to let AI extract linked fields automatically.</p>
                  </div>
                  <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-2 mb-2">
                    <div className="h-10 w-10 shrink-0 rounded bg-slate-700" />
                    <div>
                      <p className="text-xs text-white">Front-cam_2024-11-14.mp4</p>
                      <p className="text-xs text-slate-400">Captured · 4.2 MB</p>
                    </div>
                  </div>
                  <button className="mt-2 w-full rounded-lg bg-sky-600 py-2 text-xs font-semibold text-white">
                    ✦ Extract &amp; Autofill
                  </button>
                </div>
              </div>
            </div>

            {/* Right: feature bullets */}
            <div className="flex flex-col justify-center p-8 sm:p-12 lg:border-l lg:border-white/10">
              <h3 className="text-xl font-semibold text-white mb-6">
                Instant evidence collection, powered by AI
              </h3>
              <ul className="space-y-5" aria-label="AI feature list">
                {[
                  {
                    title: "Auto-extract from video",
                    body: "AI analyzes footage and pre-fills incident fields — speed, location, time of impact, and more.",
                  },
                  {
                    title: "Risk scoring on every incident",
                    body: "Each event is scored for severity and litigation risk so your team focuses where it matters most.",
                  },
                  {
                    title: "Behavior pattern detection",
                    body: "Surface coaching opportunities before they become claims with fleet-wide trend analysis.",
                  },
                  {
                    title: "Chain-of-custody automation",
                    body: "Every file access and export is logged and timestamped automatically — no manual tracking needed.",
                  },
                ].map((feat) => (
                  <li key={feat.title} className="flex gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 text-xs">✓</span>
                    <div>
                      <p className="text-sm font-semibold text-white">{feat.title}</p>
                      <p className="mt-0.5 text-sm text-slate-400">{feat.body}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </MarketingContainer>
    </section>
  );
}
