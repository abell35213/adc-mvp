import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";

export function DemoSection() {
  return (
    <MarketingSection id="demo" className="bg-[#EBF2FA]">
      <div className="text-center space-y-4 mb-10">
        <h2 className="text-4xl font-bold tracking-tight text-[#062040] sm:text-5xl">
          Take a self-guided tour of ADC
        </h2>
        <p className="text-slate-500 max-w-xl mx-auto">
          Interact with our solutions firsthand and see the full impact on your people, assets, and operations.
        </p>
      </div>

      {/* Product screenshot mockup */}
      <div className="relative rounded-2xl overflow-hidden border border-slate-200 shadow-xl bg-[#062040]">
        {/* Fake browser chrome */}
        <div className="flex items-center gap-2 bg-[#0A2A50] px-4 py-3 border-b border-slate-700/60">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-red-500/70" />
            <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
            <span className="h-3 w-3 rounded-full bg-green-500/70" />
          </div>
          <span className="ml-3 text-xs text-slate-400 font-medium">
            Review Trip Media — Truck 101 · Nov 10
          </span>
        </div>

        {/* Dashboard content */}
        <div className="grid grid-cols-[200px_1fr] min-h-[340px]">
          {/* Sidebar */}
          <div className="bg-[#0A2A50] p-4 border-r border-slate-700/40 space-y-3">
            <div className="text-center">
              <p className="text-4xl font-bold text-white">14</p>
              <p className="text-[10px] text-slate-400">mph</p>
            </div>
            <div className="mt-4 h-28 rounded-lg bg-slate-700/50 flex items-center justify-center text-slate-500 text-xs">
              📹 Video
            </div>
            <div className="mt-2 space-y-2 text-[10px] text-slate-400">
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded-full bg-[#1B6EF3] flex items-center justify-center text-[8px] text-white font-bold">B</div>
                <span>Nov 10, 2:26 PM EST</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-4 w-4 rounded-full bg-slate-500 flex items-center justify-center text-[8px] text-white font-bold">A</div>
                <span>Nov 10, 2:25 PM EST</span>
              </div>
            </div>
          </div>

          {/* Main area */}
          <div className="relative p-4">
            {/* Tooltip overlay */}
            <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-white rounded-xl shadow-xl p-4 max-w-xs w-full border border-slate-200 z-10">
              <p className="text-xs text-slate-700 leading-5">
                You can further customize the video by adjusting the start and finish times to ensure you capture exactly what you need. Once finalized, the video will be ready in your inbox.
              </p>
              <div className="flex justify-end gap-2 mt-3">
                <button className="text-xs px-3 py-1 rounded border border-slate-300 text-slate-600">Back</button>
                <button className="text-xs px-3 py-1 rounded bg-[#062040] text-white">Next</button>
              </div>
            </div>

            {/* Map area */}
            <div className="mt-20 h-40 rounded-lg bg-green-50 border border-green-200 flex items-center justify-center text-green-700 text-sm">
              🗺️ Route & GPS map
            </div>

            {/* Timeline bar */}
            <div className="mt-3 h-2 rounded-full bg-slate-700/40">
              <div className="h-full w-2/3 rounded-full bg-[#1B6EF3]/60" />
            </div>
            <div className="flex justify-between text-[10px] text-slate-400 mt-1">
              <span>2:15 PM</span><span>2:20 PM</span><span>2:25 PM</span><span>2:30 PM</span>
            </div>
          </div>
        </div>

        {/* CTA overlay button */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <Link
            href="/company/contact"
            className="pointer-events-auto inline-flex items-center gap-2 rounded-full bg-[#1B6EF3] px-6 py-3 text-sm font-bold text-white shadow-lg transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            aria-label="Explore interactive demo"
          >
            Explore interactive demo
            <span aria-hidden="true" className="rounded-full bg-white/20 h-6 w-6 flex items-center justify-center text-xs">↗</span>
          </Link>
        </div>
      </div>
    </MarketingSection>
  );
}
