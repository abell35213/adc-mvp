import type { ReactNode } from "react";

export interface ErrorStateBannerProps {
  title?: string;
  message: string;
  action?: ReactNode;
  className?: string;
}

export default function ErrorStateBanner({
  title = "Unable to load this view",
  message,
  action,
  className,
}: ErrorStateBannerProps) {
  return (
    <section
      className={[
        "rounded-lg border border-status-critical/40 bg-status-critical-soft/60 p-4",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      role="alert"
      aria-live="assertive"
    >
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_18rem] xl:items-start">
        <div>
          <h3 className="text-sm font-semibold text-status-critical">{title}</h3>
          <p className="mt-1 text-sm text-text-primary">{message}</p>

          <div className="mt-3 flex flex-wrap items-center gap-2">{action}</div>
        </div>

        <aside className="rounded-md border border-status-critical/30 bg-surface p-3 md:order-first xl:order-none">
          <p className="text-xs font-semibold uppercase tracking-wide text-status-critical">Operator guidance</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-text-secondary">
            <li>Retry after confirming connectivity.</li>
            <li>Use wrapped tablet filters to narrow affected rows.</li>
            <li>Switch to mobile cards if table rendering fails.</li>
          </ul>
        </aside>
      </div>
    </section>
  );
}
