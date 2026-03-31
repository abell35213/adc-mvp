import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function Hero() {
  return (
    <header className="bg-white border-b border-slate-200/80">
      {/* Navigation */}
      <MarketingContainer>
        <nav className="flex items-center justify-between py-5" aria-label="Primary">
          <Link href="/" className="text-lg font-bold tracking-tight text-slate-900">
            ADC
          </Link>
          <ul className="hidden items-center gap-8 text-sm font-medium text-slate-600 md:flex" role="list">
            <li><Link className="hover:text-slate-900 transition" href="/product">Platform</Link></li>
            <li><Link className="hover:text-slate-900 transition" href="/solutions">Solutions</Link></li>
            <li><Link className="hover:text-slate-900 transition" href="/pricing">Pricing</Link></li>
            <li><Link className="hover:text-slate-900 transition" href="/resources">Resources</Link></li>
          </ul>
          <div className="flex items-center gap-3">
            <Link className={marketingTokens.buttonVariants.secondary} href="/login" aria-label="Sign in to your account">
              Sign in
            </Link>
            <Link className={marketingTokens.buttonVariants.primary} href="/company/contact" aria-label="Book a demo">
              Book a demo
            </Link>
          </div>
        </nav>
      </MarketingContainer>

      {/* Hero content */}
      <div className="bg-[#0a1628] py-20 sm:py-28">
        <MarketingContainer>
          <div className="mx-auto max-w-4xl text-center">
            <span className={marketingTokens.badgeLight}>
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
              Fleet Safety &amp; Compliance
            </span>
            <h1 className="mt-6 text-5xl font-semibold tracking-tight text-white sm:text-6xl lg:text-7xl">
              Reduce claim exposure with evidence-ready incident operations.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              ADC gives fleet safety, risk, and operations leaders one workflow for incident intake,
              evidence retention, and insurer-ready exports.
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Link className={marketingTokens.buttonVariants.primaryLight} href="/company/contact" aria-label="Book a product demo">
                Book a demo
              </Link>
              <Link className={marketingTokens.buttonVariants.secondaryLight} href="/product" aria-label="View the ADC platform">
                View platform →
              </Link>
            </div>
          </div>

          {/* Dashboard preview placeholder */}
          <div className="mx-auto mt-16 max-w-5xl rounded-2xl border border-white/10 bg-[#0f2040] p-2 shadow-2xl ring-1 ring-white/5">
            <div className="flex items-center gap-1.5 px-3 py-2">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-green-500/70" />
            </div>
            <div className="rounded-xl bg-[#0a1628] p-6 sm:p-10">
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  { label: "Open Incidents", value: "12", sub: "3 require action" },
                  { label: "Evidence Packets", value: "94%", sub: "Complete & audit-ready" },
                  { label: "Avg. Closure Time", value: "2.1 days", sub: "↓ 34% vs last quarter" },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <p className="text-xs font-medium text-slate-400">{stat.label}</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{stat.value}</p>
                    <p className="mt-1 text-xs text-slate-400">{stat.sub}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs font-medium text-slate-400 mb-3">Recent Incidents</p>
                  {["Highway 101 rear-end — video captured", "Warehouse loading dock — awaiting review", "City route collision — packet sent"].map((item) => (
                    <div key={item} className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-0">
                      <span className="h-1.5 w-1.5 rounded-full bg-sky-400 shrink-0" />
                      <span className="text-xs text-slate-300">{item}</span>
                    </div>
                  ))}
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                  <p className="text-xs font-medium text-slate-400 mb-3">Evidence Chain Status</p>
                  {[
                    { label: "Video footage", pct: 92 },
                    { label: "Telematics data", pct: 100 },
                    { label: "Driver statements", pct: 75 },
                  ].map((item) => (
                    <div key={item.label} className="mb-3 last:mb-0">
                      <div className="flex justify-between text-xs text-slate-400 mb-1">
                        <span>{item.label}</span><span>{item.pct}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/10">
                        <div className="h-1.5 rounded-full bg-sky-500" style={{ width: `${item.pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </MarketingContainer>
      </div>
    </header>
  );
}
