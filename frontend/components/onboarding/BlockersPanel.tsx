import Link from "next/link";

type Blocker = {
  code: string;
  title: string;
  detail: string;
  severity: "critical" | "warning" | "info";
};

type BlockersPanelProps = {
  blockers: Blocker[];
  reviewHref: string;
};

const SEVERITY_STYLES: Record<Blocker["severity"], string> = {
  critical: "border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-200",
  warning: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200",
  info: "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200",
};

export default function BlockersPanel({ blockers, reviewHref }: BlockersPanelProps) {
  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Blockers</h3>
        <Link href={reviewHref} className="text-xs font-medium text-blue-600 hover:underline">
          Review blockers
        </Link>
      </div>

      {blockers.length === 0 ? (
        <p className="text-xs text-emerald-700 dark:text-emerald-300">No blockers detected.</p>
      ) : (
        <ul className="space-y-2">
          {blockers.slice(0, 4).map((blocker) => (
            <li key={blocker.code} className={`rounded-md border p-2 text-xs ${SEVERITY_STYLES[blocker.severity]}`}>
              <p className="font-semibold">{blocker.title}</p>
              <p className="mt-1">{blocker.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
