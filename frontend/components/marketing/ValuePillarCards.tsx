import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const features = [
  {
    eyebrow: "Fleet Telematics",
    title: "Fleet Telematics",
    body: "Get GPS, fuel, routing, and maintenance data to boost efficiency and support safety.",
    visual: (
      <div className="rounded-xl bg-[#F4F8FC] p-6 border border-slate-200">
        <p className="text-sm font-semibold text-[#062040] mb-3">Oil Change</p>
        <div className="space-y-3 text-sm text-slate-600">
          <div className="flex justify-between border-b border-slate-200 pb-2">
            <span>Labor Hours</span>
            <span className="font-medium text-[#062040]">1.50 hr</span>
          </div>
          <div className="flex justify-between pt-2">
            <span>Labor Rate</span>
            <span className="font-medium text-[#062040]">$150.00</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Mobile Apps",
    title: "Mobile Apps",
    body: "Mobile tools for safety, compliance, logs, inspections, coaching, and simplified workflows.",
    visual: (
      <div className="rounded-xl bg-[#062040] p-6 text-white">
        <p className="text-sm font-semibold mb-4 text-center">ADC</p>
        <div className="flex gap-3 justify-center">
          {["Driver", "Fleet", "Sites"].map((app) => (
            <div key={app} className="flex flex-col items-center gap-1">
              <div className="h-12 w-12 rounded-xl bg-[#1B6EF3]/30 border border-[#1B6EF3]/50 flex items-center justify-center text-lg">
                {app === "Driver" ? "🦉" : app === "Fleet" ? "🧭" : "📊"}
              </div>
              <span className="text-[10px] text-slate-300">ADC {app}</span>
            </div>
          ))}
        </div>
      </div>
    ),
  },
];

export function ValuePillarCards() {
  return (
    <MarketingSection className="bg-white">
      {/* Feature tiles row */}
      <div className="grid gap-10 lg:grid-cols-2">
        {features.map(({ title, body, visual }) => (
          <div key={title} className="grid gap-6 md:grid-cols-2 items-center">
            <div>{visual}</div>
            <div>
              <h3 className={marketingTokens.headingScale.h3}>{title}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">{body}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Stats row */}
      <dl className="mt-16 grid gap-8 text-center sm:grid-cols-3">
        {[
          { value: "250K+", label: "accidents prevented in FY25" },
          { value: "3B+", label: "miles of safety data analyzed" },
          { value: "300M+", label: "frontline workflows digitized" },
        ].map(({ value, label }) => (
          <div key={label}>
            <dt className="text-6xl font-bold tracking-tight text-[#062040]">{value}</dt>
            <dd className="mt-2 text-sm text-slate-500 max-w-[14rem] mx-auto leading-6">{label}</dd>
          </div>
        ))}
      </dl>
    </MarketingSection>
  );
}
