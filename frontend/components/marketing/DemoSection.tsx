import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function DemoSection() {
  return (
    <MarketingSection id="demo">
      <div className={`${marketingTokens.surfaces.accent} rounded-3xl px-8 py-14 sm:px-14`}>
        <div className="mx-auto max-w-2xl space-y-4 text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Get pricing in minutes
          </h2>
          <p className="text-sky-200">
            Tell us your fleet size and we&apos;ll send a tailored quote—no sales call required to
            get started.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link
              href="/pricing"
              className="inline-flex items-center justify-center rounded-md bg-white px-6 py-3 text-sm font-semibold text-sky-900 shadow-sm transition hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              aria-label="View pricing plans"
            >
              Get Pricing
            </Link>
            <Link
              href="/company/contact"
              className="inline-flex items-center justify-center rounded-md border border-sky-400 px-6 py-3 text-sm font-semibold text-white transition hover:bg-sky-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              aria-label="Book a product demo"
            >
              Book Demo
            </Link>
          </div>
          <p className="pt-2 text-xs text-sky-300">
            <span aria-hidden="true">★★★★★</span>
            <span className="sr-only">5 out of 5 stars.</span>
            {" "}Rated 4.9 / 5 by 200+ fleet operators
          </p>
        </div>
      </div>
    </MarketingSection>
  );
}
