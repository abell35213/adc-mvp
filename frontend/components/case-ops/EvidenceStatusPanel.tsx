interface EvidenceStatusPanelProps {
  captured: number;
  pending: number;
  unavailable: number;
  total: number;
}

export default function EvidenceStatusPanel({ captured, pending, unavailable, total }: EvidenceStatusPanelProps) {
  const coverage = Math.round((captured / Math.max(total, 1)) * 100);

  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Evidence captured / missing</h3>
      <p className="mt-1 text-xs text-gray-500">Visibility into what is present and what blocks readiness.</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Captured" value={`${captured}/${total}`} />
        <Metric label="Pending" value={String(pending)} />
        <Metric label="Unavailable" value={String(unavailable)} />
        <Metric label="Coverage" value={`${coverage}%`} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-2">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="font-semibold text-gray-900">{value}</p>
    </div>
  );
}
