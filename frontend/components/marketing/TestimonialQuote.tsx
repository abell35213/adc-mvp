import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

export function TestimonialQuote() {
  return (
    <MarketingSection>
      <figure className={`${marketingTokens.surfaces.accent} p-8 sm:p-12`}>
        <blockquote className="text-xl leading-8 sm:text-2xl">
          “ADC cut our investigation prep from hours to minutes. We finally have one defensible source of truth.”
        </blockquote>
        <figcaption className="mt-6 text-sm text-sky-100">Jordan Lee, Director of Safety Operations, NorthLine Freight</figcaption>
      </figure>
    </MarketingSection>
  );
}
