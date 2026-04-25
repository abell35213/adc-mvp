import type { ReactNode } from "react";

export type SectionCardTone = "default" | "info" | "success" | "warning" | "critical";

export interface SectionCardProps {
  title: string;
  description?: string;
  tone?: SectionCardTone;
  actions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

const toneClass: Record<SectionCardTone, string> = {
  default: "border-border-default bg-surface",
  info: "border-status-info/30 bg-status-info-soft/50",
  success: "border-status-success/30 bg-status-success-soft/50",
  warning: "border-status-warning/30 bg-status-warning-soft/50",
  critical: "border-status-critical/30 bg-status-critical-soft/50",
};

export default function SectionCard({
  title,
  description,
  tone = "default",
  actions,
  children,
  footer,
  className,
}: SectionCardProps) {
  return (
    <section className={["rounded-lg border p-4 shadow-card", toneClass[tone], className].filter(Boolean).join(" ")}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-text-primary">{title}</h2>
          {description ? <p className="text-sm text-text-secondary">{description}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>

      <div>{children}</div>

      {footer ? <div className="mt-4 border-t border-border-subtle pt-3 text-sm text-text-secondary">{footer}</div> : null}
    </section>
  );
}
