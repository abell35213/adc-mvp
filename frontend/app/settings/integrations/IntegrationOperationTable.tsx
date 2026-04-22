import type { IntegrationOperationDiagnostics } from "@/lib/api";

type Props = {
  rows: IntegrationOperationDiagnostics[];
  onSelect: (row: IntegrationOperationDiagnostics) => void;
};

export default function IntegrationOperationTable({ rows, onSelect }: Props) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-50">Integration operations</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] text-left text-xs">
          <thead className="text-gray-500">
            <tr>
              <th className="py-2">Time</th>
              <th className="py-2">Org</th>
              <th className="py-2">Provider</th>
              <th className="py-2">Domain</th>
              <th className="py-2">Operation</th>
              <th className="py-2">Status</th>
              <th className="py-2">Retry count</th>
              <th className="py-2">Normalized error</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-gray-700">
            {rows.map((row) => {
              const retryFromResult = row.result_json["retry_count"];
              const retryFromPayload = row.payload_json["retry_count"];
              const retryCount = Number(
                (typeof retryFromResult === "number" ? retryFromResult : undefined) ??
                (typeof retryFromPayload === "number" ? retryFromPayload : undefined) ??
                0
              );
              const normalizedCode = row.error_category ?? row.error_code ?? "NONE";
              return (
                <tr key={row.operation_id}>
                  <td className="py-2">{row.requested_at_utc ? new Date(row.requested_at_utc).toLocaleString() : "—"}</td>
                  <td className="py-2 font-mono">{row.org_id ?? "—"}</td>
                  <td className="py-2">{row.provider}</td>
                  <td className="py-2">{row.domain ?? "—"}</td>
                  <td className="py-2">{row.operation_type}</td>
                  <td className="py-2">{row.status}</td>
                  <td className="py-2">{Number.isNaN(retryCount) ? 0 : retryCount}</td>
                  <td className="py-2">{normalizedCode}</td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => onSelect(row)}
                      className="rounded border px-2 py-1 hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="py-4 text-gray-500">No operations found for these filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
