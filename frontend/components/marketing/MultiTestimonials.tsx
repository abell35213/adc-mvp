import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const testimonials = [
  {
    quote:
      "With ADC, we're not just tracking vehicles and incidents—we're protecting our entire operation. It's given us the tools we need to be more efficient, reduce claim costs, and stay ahead.",
    name: "Jordan Lee",
    title: "CEO, NorthLine Freight",
    company: "NorthLine Freight",
    abbr: "NLF",
  },
  {
    quote:
      "I can physically point to claims we would have lost without ADC's evidence packages. The platform paid for itself in our first contested case.",
    name: "Maria Santos",
    title: "Director of Risk Management, Summit Logistics",
    company: "Summit Logistics",
    abbr: "SL",
  },
];

export function MultiTestimonials() {
  return (
    <MarketingSection className="bg-white">
      <h2 className={`${marketingTokens.headingScale.h2} text-center mb-12`}>
        Driving real impact for our customers
      </h2>
      <div className="grid gap-6 md:grid-cols-2">
        {testimonials.map(({ quote, name, title, abbr }) => (
          <figure
            key={name}
            className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
          >
            <blockquote className="text-base leading-8 text-slate-700">
              &ldquo;{quote}&rdquo;
            </blockquote>
            <figcaption className="mt-6 flex items-center gap-4">
              <div className="h-10 w-10 shrink-0 rounded-full bg-[#062040] flex items-center justify-center text-white text-xs font-bold">
                {abbr}
              </div>
              <div>
                <p className="text-sm font-semibold text-[#062040]">{name}</p>
                <p className="text-xs text-slate-500">{title}</p>
              </div>
            </figcaption>
          </figure>
        ))}
      </div>

      {/* Navigation arrow */}
      <div className="flex justify-end mt-6">
        <button
          className="h-10 w-10 rounded-full bg-[#062040] text-white flex items-center justify-center hover:bg-[#0a3060] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#062040] focus-visible:ring-offset-2"
          aria-label="View more testimonials"
        >
          →
        </button>
      </div>
    </MarketingSection>
  );
}
