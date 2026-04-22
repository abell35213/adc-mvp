interface EvidenceStatusPanelProps {
  captured: number;
  pending: number;
  unavailable: number;
  total: number;
}

export default function EvidenceStatusPanel({ captured, pending, unavailable, total }: EvidenceStatusPanelProps) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow dark:bg-gray-800">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Evidence status</h3>
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Captured" value={`${captured}/${total}`} />
        <Metric label="Pending" value={String(pending)} />
        <Metric label="Unavailable" value={String(unavailable)} />
        <Metric label="Coverage" value={`${Math.round((captured / Math.max(total, 1)) * 100)}%`} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border bg-gray-50 p-2 dark:bg-gray-700">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="font-semibold text-gray-900 dark:text-white">{value}</p>
    </div>
  );
}
