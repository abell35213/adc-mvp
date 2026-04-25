import type { ReactNode } from "react";

export interface RightRailPanelProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export default function RightRailPanel({ title, subtitle, children, actions, className }: RightRailPanelProps) {
  return (
    <section className={["rounded-lg border border-border-default bg-surface p-4 shadow-card", className].filter(Boolean).join(" ")}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">{title}</h3>
          {subtitle ? <p className="mt-1 text-xs text-text-muted">{subtitle}</p> : null}
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
