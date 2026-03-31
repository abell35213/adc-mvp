import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function CTASection() {
  return (
    <section id="contact" className="bg-[#0a1628] py-14 sm:py-18 lg:py-24">
      <MarketingContainer>
        <div className="rounded-3xl border border-white/10 bg-[#0f2040] p-10 text-center sm:p-16">
          <h2 className={`${marketingTokens.headingScale.h2Light} mx-auto max-w-2xl`}>
            Ready to modernize fleet incident response?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-slate-300">
            Launch in days with migration support and guided onboarding. Join 120+ fleets already protecting themselves with ADC.
          </p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link href="/company/contact" className={marketingTokens.buttonVariants.primaryLight} aria-label="Book a product demo">
              Book a demo
            </Link>
            <Link href="/pricing" className={marketingTokens.buttonVariants.secondaryLight} aria-label="View pricing plans">
              View pricing
            </Link>
          </div>
        </div>
      </MarketingContainer>
    </section>
  );
}
