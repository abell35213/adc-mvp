interface MissingItemsPanelProps {
  items: string[];
}

export default function MissingItemsPanel({ items }: MissingItemsPanelProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Missing evidence</h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-green-700">No missing evidence items.</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
