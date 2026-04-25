import StatusChip, { type StatusChipSize } from "./StatusChip";

export type SeverityLevel = "low" | "medium" | "high" | "critical";

export interface SeverityBadgeProps {
  severity: SeverityLevel;
  size?: StatusChipSize;
  className?: string;
}

const TONES: Record<SeverityLevel, "neutral" | "info" | "warning" | "critical"> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "critical",
};

export default function SeverityBadge({ severity, size = "md", className }: SeverityBadgeProps) {
  return <StatusChip label={severity[0].toUpperCase() + severity.slice(1)} tone={TONES[severity]} size={size} className={className} />;
}
