import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function Hero() {
  return (
    <header className="border-b border-slate-200/80">
      <MarketingContainer>
        <nav className="flex items-center justify-between py-6" aria-label="Primary">
          <span className="text-sm font-semibold uppercase tracking-[0.2em] text-sky-700">ADC</span>
          <ul className="hidden items-center gap-6 text-sm text-slate-700 md:flex" role="list">
            <li><a className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2" href="#features">Features</a></li>
            <li><a className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2" href="#pricing">Pricing</a></li>
            <li><a className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2" href="#contact">Contact</a></li>
          </ul>
          <Link className={marketingTokens.buttonVariants.secondary} href="/login" aria-label="Sign in to your account">
            Sign in
          </Link>
        </nav>

        <div className="grid gap-10 py-14 lg:grid-cols-[1.15fr_1fr] lg:items-center lg:py-20">
          <div className="space-y-6">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-sky-700">Safety + operations intelligence</p>
            <h1 className={marketingTokens.headingScale.display}>Faster fleet investigations with audit-ready evidence.</h1>
            <p className={marketingTokens.headingScale.body}>
              Centralize incidents, telematics, and chain-of-custody exports in one place your safety team can trust.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link className={marketingTokens.buttonVariants.primary} href="/login" aria-label="Start a free fleet trial">
                Start free trial
              </Link>
              <a className={marketingTokens.buttonVariants.secondary} href="#pricing" aria-label="Jump to pricing plans">
                View pricing
              </a>
            </div>
          </div>

          <form className={`${marketingTokens.surfaces.card} space-y-4`} aria-label="Request demo form">
            <h2 className={marketingTokens.headingScale.h3}>Request a walkthrough</h2>
            <label className="block text-sm font-medium text-slate-800" htmlFor="work-email">Work email</label>
            <input
              id="work-email"
              name="email"
              type="email"
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              placeholder="you@fleetco.com"
            />
            <button type="submit" className={`${marketingTokens.buttonVariants.primary} w-full`} aria-label="Submit demo request">
              Request demo
            </button>
          </form>
        </div>
      </MarketingContainer>
    </header>
  );
}
