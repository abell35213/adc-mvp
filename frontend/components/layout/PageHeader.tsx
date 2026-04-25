import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}

export default function PageHeader({ title, subtitle, eyebrow, actions, meta, className }: PageHeaderProps) {
  return (
    <header className={["rounded-lg border border-border-default bg-surface p-5 shadow-card", className].filter(Boolean).join(" ")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          {eyebrow ? <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{eyebrow}</p> : null}
          <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
          {subtitle ? <p className="text-sm text-text-secondary">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="mt-4 border-t border-border-subtle pt-3 text-xs text-text-secondary">{meta}</div> : null}
    </header>
  );
}
