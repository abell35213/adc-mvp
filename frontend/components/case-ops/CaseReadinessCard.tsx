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

export function ExportReadinessBanner({
  blockersCount,
  readinessState,
  blockers = [],
}: {
  blockersCount: number;
  readinessState: string;
  blockers?: ReadinessBlocker[];
}) {
  const topReasons = blockers
    .filter((blocker) => blocker.blocks_readiness !== false)
    .slice(0, 2)
    .map((blocker) => blocker.message || blocker.code || "Unspecified readiness blocker");

  if (readinessState === "ready_for_export" || readinessState === "exported" || blockersCount === 0) {
    return <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">Export readiness: no blockers detected.</div>;
  }

  if (readinessState === "conditionally_ready") {
    return (
      <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
        <p>Export readiness: conditionally ready. {blockersCount} blocker{blockersCount === 1 ? "" : "s"} may affect packet completeness.</p>
        {topReasons.length > 0 && (
          <ul className="mt-1 list-disc pl-5 text-xs">
            {topReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      <p>Export readiness: blocked. Resolve readiness blockers before requesting export.</p>
      {topReasons.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs">
          {topReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CaseReadinessCard({ readinessState, completenessPercent, blockersCount }: CaseReadinessCardProps) {
  return (
    <div className="rounded-md border bg-gray-50 p-3 dark:bg-gray-900/40">
      <p className="text-xs text-gray-500">Readiness</p>
      <p className="mt-1 text-sm font-semibold capitalize text-gray-900 dark:text-white">{readinessState.replaceAll("_", " ")}</p>
      <p className="text-xs text-gray-600 dark:text-gray-300">Completeness {completenessPercent}% · {blockersCount} blocker{blockersCount === 1 ? "" : "s"}</p>
    </div>
  );
}
