import { statusBadgeClass, type StatusTone } from "@/lib/design/tokens";

export type StatusChipSize = "sm" | "md" | "lg";

export interface StatusChipProps {
  label: string;
  tone?: StatusTone;
  size?: StatusChipSize;
  className?: string;
}

const sizeClass: Record<StatusChipSize, string> = {
  sm: "text-[11px] px-2 py-0.5",
  md: "text-xs px-2.5 py-1",
  lg: "text-sm px-3 py-1",
};

export default function StatusChip({ label, tone = "neutral", size = "md", className }: StatusChipProps) {
  return <span className={[statusBadgeClass(tone), sizeClass[size], className].filter(Boolean).join(" ")}>{label}</span>;
}
