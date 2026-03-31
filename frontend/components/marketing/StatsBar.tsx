import { MarketingSection } from "@/components/marketing/LayoutPrimitives";

const stats = [
  { value: "250K+", label: "incidents documented" },
  { value: "34%", label: "faster evidence turnaround" },
  { value: "22%", label: "lower average claim payout" },
  { value: "2.5×", label: "coaching follow-through" },
];

export function StatsBar() {
  return (
    <MarketingSection className="bg-sky-900 py-14 text-white">
      <ul
        className="grid gap-y-10 text-center sm:grid-cols-2 lg:grid-cols-4"
        aria-label="Platform impact statistics"
      >
        {stats.map(({ value, label }) => (
          <li key={label}>
            <p className="text-4xl font-bold tracking-tight">{value}</p>
            <p className="mt-1 text-sm font-medium text-sky-200">{label}</p>
          </li>
        ))}
      </ul>
    </MarketingSection>
  );
}
