export type StatusTone = "neutral" | "info" | "success" | "warning" | "critical";

const statusBadgeClasses: Record<StatusTone, string> = {
  neutral: "bg-surface-muted text-text-secondary",
  info: "bg-status-info-soft text-status-info",
  success: "bg-status-success-soft text-status-success",
  warning: "bg-status-warning-soft text-status-warning",
  critical: "bg-status-critical-soft text-status-critical",
};

export const designTokens = {
  shell: "bg-shell text-text-inverse",
  page: "bg-page text-text-primary",
  surface: {
    base: "rounded-lg border border-border-default bg-surface shadow-card",
    subtle: "rounded-lg border border-border-subtle bg-surface-muted",
    elevated: "rounded-lg border border-border-default bg-surface-elevated shadow-card",
    panel: "bg-surface-elevated shadow-panel",
  },
  border: {
    default: "border-border-default",
    subtle: "border-border-subtle",
    strong: "border-border-strong",
  },
  text: {
    primary: "text-text-primary",
    secondary: "text-text-secondary",
    muted: "text-text-muted",
    inverse: "text-text-inverse",
  },
  accent: {
    solid: "bg-accent text-text-inverse hover:bg-accent-strong",
    soft: "bg-accent-soft text-accent",
    text: "text-accent hover:text-accent-strong",
  },
  radius: {
    sm: "rounded-sm",
    md: "rounded-md",
    lg: "rounded-lg",
    xl: "rounded-xl",
  },
  shadow: {
    card: "shadow-card",
    cardHover: "hover:shadow-card-hover",
    panel: "shadow-panel",
  },
  status: {
    badgeBase: "rounded-full px-2 py-0.5 text-xs font-medium",
    badge: statusBadgeClasses,
  },
  control: {
    input: "rounded-md border border-border-default bg-surface px-2 py-1 text-sm text-text-primary",
    link: "text-accent hover:text-accent-strong hover:underline",
    buttonSecondary: "rounded-md border border-border-default bg-surface px-2 py-1 text-xs text-text-secondary hover:bg-surface-muted",
  },
} as const;

export function statusBadgeClass(tone: StatusTone): string {
  return `${designTokens.status.badgeBase} ${designTokens.status.badge[tone]}`;
}
