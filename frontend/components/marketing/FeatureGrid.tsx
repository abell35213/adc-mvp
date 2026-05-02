import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const features = [
  {
    title: "Incident-triggered capture via telematics & driver app",
    body: "Trigger evidence capture from telematics events, then let drivers upload photos, docs, and statements so every incident starts with complete proof.",
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
    title: "Hash-verified chain-of-custody timeline",
    body: "Every file action is logged, signed, and hashed so risk teams can show exactly who touched evidence, when, and whether anything changed.",
    dark: false,
    visual: (
      <div className="rounded-xl bg-[#F4F8FC] p-4 border border-slate-200">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-slate-500">Evidence chain-of-custody</p>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
            VERIFIED
          </span>
        </div>
        <ol className="space-y-3 text-[11px] text-slate-600" role="list" aria-label="Custody timeline">
          {[
            { time: "14:02:17", actor: "Telematics", action: "Event captured", chip: "SHA-256 9f3a…b2e1" },
            { time: "14:02:42", actor: "Driver app", action: "Photos uploaded (4)", chip: "SHA-256 1d77…04ac" },
            { time: "14:08:05", actor: "Risk analyst", action: "Reviewed & sealed", chip: "SHA-256 8b21…77df" },
            { time: "14:31:22", actor: "Exports", action: "Insurer packet generated", chip: "SHA-256 c5e0…9120" },
          ].map(({ time, actor, action, chip }) => (
            <li key={time} className="flex items-start gap-3">
              <span className="mt-0.5 h-2 w-2 rounded-full bg-[#1B6EF3] shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-[#062040]">{actor}</span>
                  <span className="font-mono text-[10px] text-slate-400">{time}</span>
                </div>
                <p>{action}</p>
                <p className="font-mono text-[10px] text-slate-400 truncate">{chip}</p>
              </div>
            </li>
          ))}
        </ol>
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
