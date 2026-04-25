import { designTokens } from "@/lib/design/tokens";

interface SummaryItem {
  label: string;
  value: string;
  detail?: string;
}

interface CommercialSummaryCardsProps {
  items: SummaryItem[];
}

export default function CommercialSummaryCards({ items }: CommercialSummaryCardsProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <article key={item.label} className={`${designTokens.surface.base} p-4`}>
          <p className="text-xs uppercase tracking-wide text-text-muted">{item.label}</p>
          <p className="mt-1 text-xl font-semibold text-text-primary">{item.value}</p>
          {item.detail ? <p className="mt-1 text-xs text-text-secondary">{item.detail}</p> : null}
        </article>
      ))}
    </div>
  );
}
