import Link from "next/link";
import type { ReactNode } from "react";

export interface EmptyStateCardProps {
  title: string;
  message: string;
  actionLabel?: string;
  actionHref?: string;
  secondaryAction?: ReactNode;
  icon?: ReactNode;
  className?: string;
}

export default function EmptyStateCard({
  title,
  message,
  actionLabel,
  actionHref,
  secondaryAction,
  icon,
  className,
}: EmptyStateCardProps) {
  return (
    <section
      className={[
        "rounded-lg border border-border-default bg-surface p-4 shadow-card",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      role="status"
      aria-live="polite"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            {icon ? <div className="mt-0.5 text-text-secondary">{icon}</div> : null}
            <div>
              <h3 className="text-base font-semibold text-text-primary">{title}</h3>
              <p className="mt-1 text-sm text-text-secondary">{message}</p>
            </div>
          </div>

          <div className="md:hidden">
            <div className="-mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-1">
              {["Readiness", "Owner", "Next action"].map((label) => (
                <div key={label} className="min-w-[10rem] snap-start rounded-md border border-border-subtle bg-surface-raised p-3">
                  <p className="text-xs text-text-muted">{label}</p>
                  <p className="mt-1 text-sm font-medium text-text-primary">No data yet</p>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {actionLabel && actionHref ? (
              <Link
                href={actionHref}
                className="rounded-md border border-status-info/40 bg-status-info-soft px-3 py-2 text-sm font-medium text-status-info hover:opacity-90"
              >
                {actionLabel}
              </Link>
            ) : null}
            {secondaryAction}
          </div>
        </div>

        <aside className="space-y-2 rounded-md border border-border-subtle bg-surface-raised p-3 md:order-first xl:order-none">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Filter controls</p>
          <p className="text-xs text-text-muted">Use filters to broaden the queue, or open drawer controls on mobile.</p>
          <button
            type="button"
            aria-label="Open filter drawer"
            aria-controls="mobile-filter-drawer"
            className="inline-flex rounded border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-secondary md:hidden"
          >
            Open filters
          </button>
        </aside>
      </div>
    </section>
  );
}
