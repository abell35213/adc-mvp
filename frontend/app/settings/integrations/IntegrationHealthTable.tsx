import type { IntegrationHealthCards, IntegrationHealthSummary } from "./page";

type Props = {
  rows: IntegrationHealthSummary[];
  cards: IntegrationHealthCards;
};

function asPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

const toneByType = {
  connected: "border-emerald-200 bg-emerald-50 text-emerald-800",
  validationErrors: "border-amber-200 bg-amber-50 text-amber-800",
  needsReauth: "border-orange-200 bg-orange-50 text-orange-800",
  recentFailures: "border-red-200 bg-red-50 text-red-800",
} as const;

export default function IntegrationHealthTable({ rows, cards }: Props) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-50">Integration health and readiness risk</h2>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-300">Use these indicators to prioritize connection fixes before evidence capture and export workflows are impacted.</p>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article className={`rounded-md border p-3 ${toneByType.connected}`}>
          <p className="text-xs font-semibold uppercase">Connected</p>
          <p className="mt-1 text-2xl font-semibold">{cards.connected}</p>
        </article>
        <article className={`rounded-md border p-3 ${toneByType.validationErrors}`}>
          <p className="text-xs font-semibold uppercase">Validation errors</p>
          <p className="mt-1 text-2xl font-semibold">{cards.validationErrors}</p>
        </article>
        <article className={`rounded-md border p-3 ${toneByType.needsReauth}`}>
          <p className="text-xs font-semibold uppercase">Needs reauth</p>
          <p className="mt-1 text-2xl font-semibold">{cards.needsReauth}</p>
        </article>
        <article className={`rounded-md border p-3 ${toneByType.recentFailures}`}>
          <p className="text-xs font-semibold uppercase">Recent failures</p>
          <p className="mt-1 text-2xl font-semibold">{cards.recentFailures}</p>
        </article>
      </div>

      <div className="mt-4 overflow-x-auto">
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
