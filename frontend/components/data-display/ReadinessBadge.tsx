import { getReadinessMeta } from "@/lib/status";
import StatusChip, { type StatusChipSize } from "./StatusChip";

export type ReadinessStatus = "not_started" | "in_progress" | "ready" | "blocked";

export interface ReadinessBadgeProps {
  status: ReadinessStatus;
  size?: StatusChipSize;
  className?: string;
}

export default function ReadinessBadge({ status, size = "md", className }: ReadinessBadgeProps) {
  const meta = getReadinessMeta(status);
  return <StatusChip label={meta.label} tone={meta.tone} size={size} className={className} />;
}
