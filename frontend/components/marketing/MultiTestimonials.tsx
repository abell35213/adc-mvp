import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const testimonials = [
  {
    quote:
      "ADC cut our investigation prep from hours to minutes. We finally have one defensible source of truth our insurers actually accept.",
    name: "Jordan Lee",
    title: "Director of Safety Operations",
    company: "NorthLine Freight",
  },
  {
    quote:
      "Before ADC we were losing winnable claims because we couldn't produce evidence fast enough. That problem is gone.",
    name: "Maria Santos",
    title: "VP of Risk Management",
    company: "Summit Logistics",
  },
  {
    quote:
      "The compliance export feature alone saved our team 15+ hours per month. Audits are no longer a fire drill.",
    name: "Derek Chung",
    title: "Fleet Safety Manager",
    company: "Apex Transport",
  },
];

export function MultiTestimonials() {
  return (
    <MarketingSection>
      <div className="space-y-3 text-center">
        <h2 className={marketingTokens.headingScale.h2}>What fleet leaders say</h2>
        <p className="text-slate-600">Real outcomes from real operations teams.</p>
      </div>
      <div className="mt-10 grid gap-6 md:grid-cols-3">
        {testimonials.map(({ quote, name, title, company }) => (
          <figure
            key={name}
            className={`${marketingTokens.surfaces.card} flex flex-col`}
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-sky-600 mb-3">
              <span aria-hidden="true">★★★★★</span>
              <span className="sr-only">5 out of 5 stars</span>
            </p>
            <blockquote className="flex-1 text-sm leading-7 text-slate-700">
              &ldquo;{quote}&rdquo;
            </blockquote>
            <figcaption className="mt-6 border-t border-slate-100 pt-4">
              <p className="text-sm font-semibold text-slate-900">{name}</p>
              <p className="text-xs text-slate-500">
                {title}, {company}
              </p>
            </figcaption>
          </figure>
        ))}
      </div>
    </MarketingSection>
  );
}
