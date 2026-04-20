interface TrustSectionCardProps {
  title: string;
  summary: string;
  highlights: string[];
}

export default function TrustSectionCard({ title, summary, highlights }: TrustSectionCardProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-base font-semibold text-gray-900 dark:text-white">{title}</h3>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{summary}</p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-200">
        {highlights.map((highlight) => (
          <li key={highlight}>{highlight}</li>
        ))}
      </ul>
    </section>
  );
}
