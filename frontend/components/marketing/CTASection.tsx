import Link from "next/link";
import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function CTASection() {
  return (
    <MarketingSection id="contact" className="pt-0">
      <div className={`${marketingTokens.surfaces.card} flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between`}>
        <div>
          <h2 className={marketingTokens.headingScale.h3}>Ready to modernize incident response?</h2>
          <p className="mt-2 text-slate-700">Launch in days with migration support and guided onboarding.</p>
        </div>
        <Link href="/login" className={marketingTokens.buttonVariants.primary} aria-label="Book a product demo">
          Book demo
        </Link>
      </div>
    </MarketingSection>
  );
}
