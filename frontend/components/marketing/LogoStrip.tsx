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
    <div className="bg-white border-y border-slate-100 py-10">
      <MarketingContainer>
        <p className="mb-6 text-center text-xs font-semibold uppercase tracking-widest text-slate-400">
          Trusted by leading fleet operators
        </p>
        <ul
          className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4"
          aria-label="Customer logos"
        >
          {logos.map((name) => (
            <li
              key={name}
              className="text-sm font-bold uppercase tracking-wider text-slate-300 transition hover:text-slate-500"
            >
              {name}
            </li>
          ))}
        </ul>
      </MarketingContainer>
    </div>
  );
}
