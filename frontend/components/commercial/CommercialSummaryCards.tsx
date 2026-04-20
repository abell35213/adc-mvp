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
        <article key={item.label} className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <p className="text-xs uppercase tracking-wide text-gray-500">{item.label}</p>
          <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">{item.value}</p>
          {item.detail ? <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">{item.detail}</p> : null}
        </article>
      ))}
    </div>
  );
}
