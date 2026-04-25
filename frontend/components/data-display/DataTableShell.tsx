import type { ReactNode } from "react";

export interface DataTableShellProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  columns: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  emptyState?: ReactNode;
  isEmpty?: boolean;
  className?: string;
}

export default function DataTableShell({
  title,
  description,
  actions,
  columns,
  children,
  footer,
  emptyState,
  isEmpty = false,
  className,
}: DataTableShellProps) {
  return (
    <section className={["rounded-lg border border-border-default bg-surface shadow-card", className].filter(Boolean).join(" ")}>
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-border-subtle p-4">
        <div>
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          {description ? <p className="text-sm text-text-secondary">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </header>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border-subtle text-sm">
          <thead className="bg-surface-muted text-left text-text-secondary">{columns}</thead>
          <tbody className="divide-y divide-border-subtle text-text-primary">{isEmpty ? null : children}</tbody>
        </table>
        {isEmpty ? <div className="p-6 text-sm text-text-secondary">{emptyState ?? "No records."}</div> : null}
      </div>

      {footer ? <footer className="border-t border-border-subtle p-3 text-xs text-text-secondary">{footer}</footer> : null}
    </section>
  );
}
