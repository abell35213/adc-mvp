interface CaseReadinessCardProps {
  readinessState: string;
  completenessPercent: number;
  blockersCount: number;
}

interface ReadinessBlocker {
  code?: string;
  message?: string;
  blocks_readiness?: boolean;
}

function readinessTone(state: string) {
  if (state === "ready_for_export" || state === "exported") return "green";
  if (state === "conditionally_ready") return "yellow";
  return "red";
}

export function ExportReadinessBanner({ blockersCount, readinessState, blockers = [] }: { blockersCount: number; readinessState: string; blockers?: ReadinessBlocker[] }) {
  const topReasons = blockers
    .filter((blocker) => blocker.blocks_readiness !== false)
    .slice(0, 2)
    .map((blocker) => blocker.message || blocker.code || "Unspecified readiness blocker");

  if (readinessState === "ready_for_export" || readinessState === "exported" || blockersCount === 0) {
    return <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">Ready for export: no blockers detected.</div>;
  }

  if (readinessState === "conditionally_ready") {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-900">
        <p>Conditionally ready: {blockersCount} blocker{blockersCount === 1 ? "" : "s"} still require review.</p>
        {topReasons.length > 0 ? (
          <ul className="mt-1 list-disc pl-5 text-xs">
            {topReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
      <p>Not ready for export: resolve blockers before packet generation.</p>
      {topReasons.length > 0 ? (
        <ul className="mt-1 list-disc pl-5 text-xs">
          {topReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default function CaseReadinessCard({ readinessState, completenessPercent, blockersCount }: CaseReadinessCardProps) {
  const tone = readinessTone(readinessState);
  const cardClass =
    tone === "green"
      ? "border-green-200 bg-green-50"
      : tone === "yellow"
        ? "border-yellow-200 bg-yellow-50"
        : "border-red-200 bg-red-50";

  return (
    <section className={`rounded-lg border p-4 ${cardClass}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-600">Ready</p>
      <p className="mt-1 text-sm font-semibold capitalize text-gray-900">{readinessState.replaceAll("_", " ")}</p>
      <p className="text-xs text-gray-700">Completeness {completenessPercent}% · {blockersCount} blocker{blockersCount === 1 ? "" : "s"}</p>
    </section>
  );
}
