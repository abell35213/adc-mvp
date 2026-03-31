import { CTASection } from "@/components/marketing/CTASection";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { Hero } from "@/components/marketing/Hero";
import { PricingTable } from "@/components/marketing/PricingTable";
import { ProofBar } from "@/components/marketing/ProofBar";
import { TestimonialQuote } from "@/components/marketing/TestimonialQuote";
import { UseCaseCards } from "@/components/marketing/UseCaseCards";
import { marketingTokens } from "@/components/marketing/tokens";

export default function MarketingPage() {
  return (
    <main className={`${marketingTokens.surfaces.page} min-h-screen`}>
      <Hero />
      <ProofBar />
      <FeatureGrid />
      <UseCaseCards />
      <TestimonialQuote />
      <PricingTable />
      <CTASection />
    </main>
  );
}
