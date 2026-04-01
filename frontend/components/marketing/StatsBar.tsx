import { MarketingSection } from "@/components/marketing/LayoutPrimitives";

const stats = [
  { value: "250K+", label: "incidents documented" },
  { value: "34%", label: "faster evidence turnaround" },
  { value: "22%", label: "lower average claim payout" },
  { value: "2.5×", label: "coaching follow-through" },
];

export function StatsBar() {
  return (
    <MarketingSection className="bg-[#EBF2FA]">
      <dl
        className="grid gap-y-12 text-center sm:grid-cols-2 lg:grid-cols-4"
        aria-label="Platform impact statistics"
      >
        {stats.map(({ value, label }) => (
          <div key={label}>
            <dt className="text-5xl font-bold tracking-tight text-[#062040]">{value}</dt>
            <dd className="mt-2 text-sm font-medium text-slate-500 max-w-[12rem] mx-auto">{label}</dd>
          </div>
        ))}
      </dl>
    </MarketingSection>
  );
}
