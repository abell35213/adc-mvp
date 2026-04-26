interface TrustSectionCardProps {
  id: string;
  title: string;
  summary: string;
  points: string[];
}

export default function TrustSectionCard({ id, title, summary, points }: TrustSectionCardProps) {
  return (
    <section id={id} className="scroll-mt-24 rounded-lg border border-border-subtle bg-surface p-4 shadow-card">
      <h3 className="text-base font-semibold text-text-primary">{title}</h3>
      <p className="mt-1 text-sm text-text-secondary">{summary}</p>
      <ul className="mt-3 space-y-2 text-sm text-text-secondary">
        {points.map((point, index) => (
          <li key={`${id}-point-${index}`} className="flex gap-2">
            <span aria-hidden className="mt-1 h-2 w-2 rounded-full bg-status-info" />
            <span>{point}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
