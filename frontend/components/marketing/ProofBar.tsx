import { MarketingSection } from "@/components/marketing/LayoutPrimitives";

const proofPoints = ["Trusted by 120+ fleets", "SOC 2 workflows", "99.9% uptime", "24/7 evidence support"];

export function ProofBar() {
  return (
    <MarketingSection className="py-8">
      <ul className="grid gap-4 text-center text-sm font-medium text-slate-700 sm:grid-cols-2 lg:grid-cols-4" aria-label="Company proof points">
        {proofPoints.map((item) => (
          <li key={item} className="rounded-full border border-slate-200 bg-white px-4 py-2">{item}</li>
        ))}
      </ul>
    </MarketingSection>
  );
}
