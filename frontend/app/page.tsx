import type { Metadata } from "next";
import { Hero } from "@/components/marketing/Hero";
import { LogoStrip } from "@/components/marketing/LogoStrip";
import { ValuePillarCards } from "@/components/marketing/ValuePillarCards";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { StatsBar } from "@/components/marketing/StatsBar";
import { DemoSection } from "@/components/marketing/DemoSection";
import { MultiTestimonials } from "@/components/marketing/MultiTestimonials";
import { ResourcesSection } from "@/components/marketing/ResourcesSection";
import { SiteFooter } from "@/components/marketing/SiteFooter";
import { buildPageMetadata } from "./marketingSeo";

export const metadata: Metadata = buildPageMetadata(
  "ADC | Fleet incident response and claims defense",
  "ADC helps fleet safety and risk teams respond faster with verifiable evidence and compliance-ready workflows.",
  "/",
);

export default function Home() {
  return (
    <>
      {/* Canonical root route: public marketing home (session-aware CTA in Hero). */}
      {/* 1. Hero — headline, subhead, 2 CTAs, trust badge */}
      <Hero />

      {/* 2. Logo strip — immediate trust signals */}
      <LogoStrip />

      {/* 3. Value pillars — Safety / Efficiency / Reliability */}
      <ValuePillarCards />

      {/* 4. Solution / feature cards */}
      <FeatureGrid />

      {/* 5. Stats bar — quantifiable proof metrics */}
      <StatsBar />

      {/* 6. Mid-page demo + pricing CTA */}
      <DemoSection />

      {/* 7. Testimonials — social proof depth */}
      <MultiTestimonials />

      {/* 8. Resources / news section */}
      <ResourcesSection />

      {/* 9. Footer with repeat CTA */}
      <SiteFooter />
    </>
  );
}
