interface MissingItemsPanelProps {
  items: string[];
}

export default function MissingItemsPanel({ items }: MissingItemsPanelProps) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow dark:bg-gray-800">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Missing items</h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-green-700">No missing items.</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-200">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
