import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const features = [
  {
    title: "AI Dash Cams and Videos",
    body: "Protect drivers and reduce costs with AI-powered video and in-cab alerts for coaching and evidence.",
    dark: true,
    visual: (
      <div className="rounded-xl bg-[#062040] p-4 text-white">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-slate-300">AI Detections:</span>
          <span className="rounded-full bg-[#1B6EF3] px-2 py-0.5 text-[10px] font-bold text-white">WET ROAD</span>
          <span className="rounded-full bg-[#1B6EF3] px-2 py-0.5 text-[10px] font-bold text-white">CONSTRUCTION</span>
        </div>
        <div className="h-32 rounded-lg bg-slate-700/60 flex items-center justify-center text-slate-400 text-xs">
          📹 Dashcam feed
        </div>
        <div className="mt-3 flex items-center gap-2">
          <div className="h-1.5 flex-1 rounded-full bg-slate-600">
            <div className="h-full w-1/3 rounded-full bg-[#1B6EF3]" />
          </div>
        </div>
      </div>
    ),
  },
  {
    title: "Equipment Tracking",
    body: "Track all assets with trusted tracking. Gain GPS location, utilization, and diagnostics to optimize.",
    dark: false,
    visual: (
      <div className="rounded-xl bg-[#F4F8FC] p-4 border border-slate-200">
        <p className="text-xs font-semibold text-slate-500 mb-2">Current Driver:</p>
        <div className="flex items-center gap-3 mb-4">
          <div className="h-10 w-10 rounded-full bg-[#062040] flex items-center justify-center text-white text-sm font-bold">
            NB
          </div>
          <span className="text-base font-bold text-[#062040]">Noah Blake</span>
        </div>
        <div className="grid grid-cols-4 gap-2 text-center text-[10px] text-slate-500 mb-4">
          {[["2:28", "Break"], ["5:28", "Drive"], ["7:15", "Shift"], ["35:48", "Cycle"]].map(([t, l]) => (
            <div key={l}>
              <div className="h-8 w-8 rounded-full border-2 border-[#1B6EF3]/30 mx-auto mb-1 flex items-center justify-center">
                <div className="h-5 w-5 rounded-full border-2 border-[#1B6EF3]" />
              </div>
              <p className="font-semibold text-[#062040]">{t}</p>
              <p>{l}</p>
            </div>
          ))}
        </div>
        <div className="h-24 rounded-lg bg-green-50 border border-green-200 flex items-center justify-center text-green-600 text-xs">
          🗺️ Route map
        </div>
      </div>
    ),
  },
];

export function FeatureGrid() {
  return (
    <MarketingSection id="features" className="bg-white">
      <div className="space-y-16">
        {features.map(({ title, body, visual }, idx) => (
          <div
            key={title}
            className={`grid gap-10 md:grid-cols-2 md:items-center ${idx % 2 === 1 ? "md:[&>*:first-child]:order-last" : ""}`}
          >
            <div>{visual}</div>
            <div className="space-y-4">
              <h2 className={marketingTokens.headingScale.h2}>{title}</h2>
              <p className="text-base leading-7 text-slate-600">{body}</p>
            </div>
          </div>
        ))}
      </div>
    </MarketingSection>
  );
}
