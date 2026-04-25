import StatusChip, { type StatusChipSize } from "./StatusChip";

export type ReadinessStatus = "not_started" | "in_progress" | "ready" | "blocked";

export interface ReadinessBadgeProps {
  status: ReadinessStatus;
  size?: StatusChipSize;
  className?: string;
}

const LABELS: Record<ReadinessStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  ready: "Ready",
  blocked: "Blocked",
};

const TONES: Record<ReadinessStatus, "neutral" | "warning" | "success" | "critical"> = {
  not_started: "neutral",
  in_progress: "warning",
  ready: "success",
  blocked: "critical",
};

export default function ReadinessBadge({ status, size = "md", className }: ReadinessBadgeProps) {
  return <StatusChip label={LABELS[status]} tone={TONES[status]} size={size} className={className} />;
}
