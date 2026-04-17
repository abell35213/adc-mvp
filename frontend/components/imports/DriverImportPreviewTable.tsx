import type { DriverPreviewRow } from "@/lib/csvImport";

type DriverImportPreviewTableProps = {
  rows: DriverPreviewRow[];
};

export default function DriverImportPreviewTable({ rows }: DriverImportPreviewTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50 text-gray-700">
          <tr>
            <th className="px-3 py-2 font-medium">First Name</th>
            <th className="px-3 py-2 font-medium">Last Name</th>
            <th className="px-3 py-2 font-medium">Phone</th>
            <th className="px-3 py-2 font-medium">Provider Driver ID</th>
            <th className="px-3 py-2 font-medium">Active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.slice(0, 12).map((row, idx) => (
            <tr key={`${row.phone}-${idx}`}>
              <td className="px-3 py-2">{row.firstName || <span className="text-red-600">Missing</span>}</td>
              <td className="px-3 py-2">{row.lastName || <span className="text-red-600">Missing</span>}</td>
              <td className="px-3 py-2">{row.phone || <span className="text-red-600">Missing</span>}</td>
              <td className="px-3 py-2">{row.providerDriverId || <span className="text-gray-400">—</span>}</td>
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
