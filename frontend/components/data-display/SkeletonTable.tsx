import type { ReactNode } from "react";

export interface SkeletonTableProps {
  title?: string;
  description?: string;
  rowCount?: number;
  columnCount?: number;
  className?: string;
  leftRail?: ReactNode;
  rightRail?: ReactNode;
}

function SkeletonBlock({ className }: { className: string }) {
  return <div className={["animate-pulse rounded bg-surface-muted", className].join(" ")} aria-hidden="true" />;
}

export default function SkeletonTable({
  title = "Loading data",
  description = "Preparing queue state, filters, and evidence readiness details.",
  rowCount = 6,
  columnCount = 5,
  className,
  leftRail,
  rightRail,
}: SkeletonTableProps) {
  return (
    <section
      className={[
        "rounded-lg border border-border-default bg-surface p-4 shadow-card",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-busy="true"
      aria-live="polite"
    >
      <div className="space-y-4">
        <header className="space-y-2">
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          <p className="text-sm text-text-secondary">{description}</p>
        </header>

        <div className="md:hidden">
          <div className="-mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-1">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={`kpi-${index}`}
                className="min-w-[11rem] snap-start rounded-lg border border-border-subtle bg-surface-raised p-3"
              >
                <SkeletonBlock className="h-3 w-20" />
                <SkeletonBlock className="mt-2 h-7 w-16" />
                <SkeletonBlock className="mt-3 h-2.5 w-full" />
              </div>
            ))}
          </div>

          <div
            aria-hidden="true"
            className="mt-3 w-full rounded-md border border-border-default px-3 py-2"
          >
            <SkeletonBlock className="h-4 w-24" />
          </div>
        </div>

        <div className="hidden items-center gap-2 md:flex md:flex-wrap">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonBlock key={`filter-${index}`} className="h-9 w-32 rounded-md" />
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-3">
            {leftRail}
            <div className="hidden overflow-x-auto rounded-lg border border-border-subtle md:block">
              <table className="min-w-[48rem] w-full">
                <thead className="bg-surface-muted">
                  <tr>
                    {Array.from({ length: columnCount }).map((_, index) => (
                      <th key={`head-${index}`} className="px-4 py-3">
                        <SkeletonBlock className="h-3 w-20" />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: rowCount }).map((_, rowIndex) => (
                    <tr key={`row-${rowIndex}`} className="border-t border-border-subtle">
                      {Array.from({ length: columnCount }).map((_, columnIndex) => (
                        <td key={`cell-${rowIndex}-${columnIndex}`} className="px-4 py-3">
                          <SkeletonBlock className="h-3 w-full max-w-[10rem]" />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="space-y-3 md:hidden">
              {Array.from({ length: rowCount }).map((_, index) => (
                <article key={`card-${index}`} className="rounded-lg border border-border-subtle p-3">
                  <SkeletonBlock className="h-4 w-32" />
                  <SkeletonBlock className="mt-3 h-3 w-full" />
                  <SkeletonBlock className="mt-2 h-3 w-11/12" />
                  <SkeletonBlock className="mt-2 h-3 w-3/4" />
                </article>
              ))}
            </div>
          </div>

          <aside className="space-y-3 md:order-first xl:order-none">
            {rightRail ?? (
              <>
                <div className="rounded-lg border border-border-subtle p-3">
                  <SkeletonBlock className="h-4 w-28" />
                  <SkeletonBlock className="mt-3 h-3 w-full" />
                  <SkeletonBlock className="mt-2 h-3 w-10/12" />
                </div>
                <div className="rounded-lg border border-border-subtle p-3">
                  <SkeletonBlock className="h-4 w-24" />
                  <SkeletonBlock className="mt-3 h-3 w-full" />
                  <SkeletonBlock className="mt-2 h-3 w-9/12" />
                </div>
              </>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}
