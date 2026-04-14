interface CaseReadinessCardProps {
  readinessState: string;
  completenessPercent: number;
  blockersCount: number;
}

export function ExportReadinessBanner({ blockersCount }: { blockersCount: number }) {
  if (blockersCount === 0) {
    return <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">Export readiness: no blockers detected.</div>;
  }
  return (
    <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
      Export readiness: {blockersCount} blocker{blockersCount === 1 ? "" : "s"} still open.
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
