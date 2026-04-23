import type { VehicleQrStats } from "@/lib/api";

type QrDeploymentTableProps = {
  stats: VehicleQrStats;
};

const rows = [
  { key: "required_vehicle_count", label: "Vehicles required" },
  { key: "generated_count", label: "QR generated" },
  { key: "distributed_count", label: "QR distributed" },
  { key: "confirmed_count", label: "Deployments confirmed" },
] as const;

export default function QrDeploymentTable({ stats }: QrDeploymentTableProps) {
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="px-3 py-2 font-medium text-gray-900">{row.label}</td>
                <td className="px-3 py-2 text-right text-gray-700">{stats[row.key]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {stats.coverage_blockers.length > 0 ? (
        <ul className="space-y-1 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {stats.coverage_blockers.map((blocker) => (
            <li key={blocker}>• {blocker}</li>
          ))}
        </ul>
      ) : (
        <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">No QR coverage blockers detected.</p>
      )}
    </div>
  );
}
