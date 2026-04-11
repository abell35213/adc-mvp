import type { IntegrationHealthSummary } from "./page";

type Props = {
  rows: IntegrationHealthSummary[];
};

function asPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default function IntegrationHealthTable({ rows }: Props) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-50">Health summary by provider / domain</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[740px] text-left text-xs">
          <thead className="text-gray-500">
            <tr>
              <th className="py-2">Provider</th>
              <th className="py-2">Domain</th>
              <th className="py-2">Success rate</th>
              <th className="py-2">Timeout rate</th>
              <th className="py-2">Stuck ops</th>
              <th className="py-2">Retries</th>
              <th className="py-2">Top normalized codes</th>
            </tr>
          </thead>
          <tbody className="divide-y dark:divide-gray-700">
            {rows.map((row) => (
              <tr key={`${row.provider}-${row.domain ?? "none"}`}>
                <td className="py-2 font-medium">{row.provider}</td>
                <td className="py-2">{row.domain ?? "—"}</td>
                <td className="py-2">{asPercent(row.successRate)}</td>
                <td className="py-2">{asPercent(row.timeoutRate)}</td>
                <td className="py-2">{row.stuckOps}</td>
                <td className="py-2">{row.retryCount}</td>
                <td className="py-2">{row.topNormalizedCodes.join(", ") || "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="py-4 text-gray-500">No operations matched the selected filters.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
