import { CTASection } from "@/components/marketing/CTASection";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { Hero } from "@/components/marketing/Hero";
import { PricingTable } from "@/components/marketing/PricingTable";
import { ProofBar } from "@/components/marketing/ProofBar";
import { TestimonialQuote } from "@/components/marketing/TestimonialQuote";
import { UseCaseCards } from "@/components/marketing/UseCaseCards";
import { AIInsightsSection } from "@/components/marketing/AIInsightsSection";
import { CustomerResults } from "@/components/marketing/CustomerResults";
import { ResourcesSection } from "@/components/marketing/ResourcesSection";
import { marketingTokens } from "@/components/marketing/tokens";

export default function MarketingPage() {
  return (
    <main className={`${marketingTokens.surfaces.page} min-h-screen`}>
      <Hero />
      <UseCaseCards />
      <AIInsightsSection />
      <ProofBar />
      <CustomerResults />
      <FeatureGrid />
      <TestimonialQuote />
      <PricingTable />
      <ResourcesSection />
      <CTASection />
    </main>
  );
}
