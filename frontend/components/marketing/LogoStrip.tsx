import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";

const logos = [
  "NorthLine Freight",
  "Summit Logistics",
  "CoreFleet Inc.",
  "Apex Transport",
  "BlueStar Carriers",
  "Horizon Fleet Co.",
];

export function LogoStrip() {
  return (
    <div className="border-y border-slate-100 bg-slate-50/60 py-8">
      <MarketingContainer>
        <p className="mb-6 text-center text-xs font-semibold uppercase tracking-widest text-slate-400">
          Trusted by leading fleet operators
        </p>
        <ul
          className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4"
          aria-label="Customer logos"
        >
          {logos.map((name) => (
            <li
              key={name}
              className="text-sm font-semibold text-slate-400 opacity-70 transition hover:opacity-100"
            >
              {name}
            </li>
          ))}
        </ul>
      </MarketingContainer>
    </div>
  );
}
