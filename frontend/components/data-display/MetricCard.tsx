import type { ReactNode } from "react";
import StatusChip, { type StatusChipSize } from "./StatusChip";
import type { StatusTone } from "@/lib/design/tokens";

export interface MetricCardProps {
  label: string;
  value: string | number;
  helperText?: string;
  tone?: StatusTone;
  trend?: {
    label: string;
    tone?: StatusTone;
    size?: StatusChipSize;
  };
  icon?: ReactNode;
  className?: string;
}

export default function MetricCard({ label, value, helperText, tone = "neutral", trend, icon, className }: MetricCardProps) {
  return (
    <article className={["rounded-lg border border-border-default bg-surface p-4 shadow-card", className].filter(Boolean).join(" ")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-text-primary">{value}</p>
        </div>
        {icon ? <div className="text-text-secondary">{icon}</div> : null}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <StatusChip label={tone} tone={tone} size="sm" />
        {trend ? <StatusChip label={trend.label} tone={trend.tone ?? tone} size={trend.size ?? "sm"} /> : null}
      </div>

      {helperText ? <p className="mt-2 text-xs text-text-secondary">{helperText}</p> : null}
    </article>
  );
}
