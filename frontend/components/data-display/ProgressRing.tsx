export type ProgressRingSize = "sm" | "md" | "lg";

export interface ProgressRingProps {
  value: number;
  max?: number;
  label?: string;
  size?: ProgressRingSize;
  tone?: "neutral" | "success" | "warning" | "critical";
  className?: string;
}

const SIZE: Record<ProgressRingSize, { box: number; stroke: number; text: string }> = {
  sm: { box: 44, stroke: 4, text: "text-[10px]" },
  md: { box: 60, stroke: 5, text: "text-xs" },
  lg: { box: 76, stroke: 6, text: "text-sm" },
};

const TONE: Record<NonNullable<ProgressRingProps["tone"]>, string> = {
  neutral: "stroke-text-secondary",
  success: "stroke-status-success",
  warning: "stroke-status-warning",
  critical: "stroke-status-critical",
};

export default function ProgressRing({
  value,
  max = 100,
  label,
  size = "md",
  tone = "neutral",
  className,
}: ProgressRingProps) {
  const config = SIZE[size];
  const radius = (config.box - config.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  const dashOffset = circumference - (pct / 100) * circumference;

  return (
    <div className={["inline-flex flex-col items-center gap-1", className].filter(Boolean).join(" ")}>
      <svg width={config.box} height={config.box} viewBox={`0 0 ${config.box} ${config.box}`} aria-label={label ?? `${pct}%`} role="img">
        <circle
          cx={config.box / 2}
          cy={config.box / 2}
          r={radius}
          fill="none"
          strokeWidth={config.stroke}
          className="stroke-border-subtle"
        />
        <circle
          cx={config.box / 2}
          cy={config.box / 2}
          r={radius}
          fill="none"
          strokeWidth={config.stroke}
          className={["origin-center -rotate-90", TONE[tone]].join(" ")}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
        />
        <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" className={config.text}>
          {pct}%
        </text>
      </svg>
      {label ? <span className="text-xs text-text-secondary">{label}</span> : null}
    </div>
  );
}
