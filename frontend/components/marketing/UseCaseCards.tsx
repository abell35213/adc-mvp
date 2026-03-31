import { MarketingSection } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const useCases = [
  { title: "Claims", copy: "Deliver complete packets before adjusters ask.", cta: "Reduce cycle time" },
  { title: "Safety", copy: "Spot recurring behavior trends and coach faster.", cta: "Lower preventables" },
  { title: "Compliance", copy: "Export evidence trails aligned with policy standards.", cta: "Pass audits" },
];

export function UseCaseCards() {
  return (
    <MarketingSection>
      <div className="grid gap-5 lg:grid-cols-3">
        {useCases.map((useCase) => (
          <article key={useCase.title} className={marketingTokens.surfaces.subtle}>
            <h3 className={marketingTokens.headingScale.h3}>{useCase.title}</h3>
            <p className="mt-2 text-slate-700">{useCase.copy}</p>
            <p className="mt-4 text-sm font-semibold text-sky-800">{useCase.cta}</p>
          </article>
        ))}
      </div>
    </MarketingSection>
  );
}
