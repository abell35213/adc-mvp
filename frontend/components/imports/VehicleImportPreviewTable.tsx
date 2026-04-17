import type { VehiclePreviewRow } from "@/lib/csvImport";

type VehicleImportPreviewTableProps = {
  rows: VehiclePreviewRow[];
};

export default function VehicleImportPreviewTable({ rows }: VehicleImportPreviewTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50 text-gray-700">
          <tr>
            <th className="px-3 py-2 font-medium">Unit Number</th>
            <th className="px-3 py-2 font-medium">VIN</th>
            <th className="px-3 py-2 font-medium">Provider Vehicle ID</th>
            <th className="px-3 py-2 font-medium">Active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.slice(0, 12).map((row, idx) => (
            <tr key={`${row.unitNumber}-${idx}`}>
              <td className="px-3 py-2">{row.unitNumber || <span className="text-red-600">Missing</span>}</td>
              <td className="px-3 py-2">{row.vin || <span className="text-amber-700">Missing</span>}</td>
              <td className="px-3 py-2">{row.providerVehicleId || <span className="text-gray-400">—</span>}</td>
              <td className="px-3 py-2">{row.isActive}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 12 && (
        <p className="border-t bg-gray-50 px-3 py-2 text-xs text-gray-500">Showing first 12 of {rows.length} rows.</p>
      )}
    </div>
  );
}
