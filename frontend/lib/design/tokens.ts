export type StatusTone = "neutral" | "informational" | "info" | "success" | "warning" | "critical";
export type ControlSize = "sm" | "md" | "lg";

const normalizedStatus = (tone: StatusTone): Exclude<StatusTone, "info"> =>
  tone === "info" ? "informational" : tone;

const statusBadgeClasses: Record<Exclude<StatusTone, "info">, string> = {
  neutral: "border-status-neutral-border bg-status-neutral-soft text-status-neutral-text",
  informational: "border-status-informational-border bg-status-informational-soft text-status-informational-text",
  success: "border-status-success-border bg-status-success-soft text-status-success-text",
  warning: "border-status-warning-border bg-status-warning-soft text-status-warning-text",
  critical: "border-status-critical-border bg-status-critical-soft text-status-critical-text",
};

export const designTokens = {
  color: {
    background: {
      canvas: "bg-canvas",
      surface: "bg-surface",
      surfaceSubtle: "bg-surface-subtle",
      surfaceRaised: "bg-surface-raised",
      surfaceInverse: "bg-surface-inverse",
    },
    text: {
      primary: "text-text-primary",
      secondary: "text-text-secondary",
      muted: "text-text-muted",
      inverse: "text-text-inverse",
      link: "text-text-link",
      disabled: "text-text-disabled",
    },
    border: {
      default: "border-border-default",
      subtle: "border-border-subtle",
      strong: "border-border-strong",
      focus: "border-border-focus",
      disabled: "border-border-disabled",
    },
  },
  shell: "bg-shell text-text-inverse",
  page: "bg-canvas text-text-primary",
  surface: {
    base: "rounded-lg border border-border-default bg-surface shadow-bordered",
    subtle: "rounded-lg border border-border-subtle bg-surface-subtle",
    elevated: "rounded-lg border border-border-default bg-surface-raised shadow-raised",
    panel: "bg-surface-raised shadow-overlay",
  },
  border: { default: "border-border-default", subtle: "border-border-subtle", strong: "border-border-strong" },
  text: { primary: "text-text-primary", secondary: "text-text-secondary", muted: "text-text-muted", inverse: "text-text-inverse" },
  accent: { solid: "bg-action-primary text-text-inverse hover:bg-action-primary-hover", soft: "bg-action-quiet text-action-primary", text: "text-text-link hover:text-action-primary-hover" },
  spacing: { 4: "1rem", 8: "2rem", 12: "3rem", 16: "4rem", 20: "5rem", 24: "6rem", 32: "8rem", 40: "10rem", 48: "12rem", 64: "16rem" },
  typography: {
    pageTitle: "text-3xl font-semibold tracking-tight text-text-primary",
    sectionTitle: "text-xl font-semibold text-text-primary",
    cardTitle: "text-base font-semibold text-text-primary",
    body: "text-sm text-text-primary",
    bodySmall: "text-xs text-text-secondary",
    metadata: "text-xs text-text-muted",
    label: "text-sm font-medium text-text-secondary",
    metric: "text-3xl font-semibold tabular-nums text-text-primary",
    code: "font-mono text-xs text-text-secondary",
  },
  radius: { sm: "rounded-sm", md: "rounded-md", lg: "rounded-lg", xl: "rounded-xl", full: "rounded-full" },
  shadow: { none: "shadow-none", bordered: "shadow-bordered", raised: "shadow-raised", overlay: "shadow-overlay" },
  control: {
    height: { sm: "h-8", md: "h-10", lg: "h-12" },
    input: "rounded-md border border-border-default bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus disabled:cursor-not-allowed disabled:border-border-disabled disabled:bg-surface-subtle disabled:text-text-disabled",
    link: "text-text-link hover:text-action-primary-hover hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2",
    buttonSecondary: "rounded-md border border-border-default bg-action-secondary px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-subtle",
  },
  icon: { xs: "size-3", sm: "size-4", md: "size-5", lg: "size-6" },
  transition: { hover: "transition-colors duration-150 motion-reduce:transition-none", focus: "transition-shadow duration-150 motion-reduce:transition-none", overlay: "transition duration-200 motion-reduce:transition-none", loading: "transition-opacity duration-150 motion-reduce:transition-none" },
  status: { badgeBase: "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium", badge: statusBadgeClasses },
} as const;

export function statusBadgeClass(tone: StatusTone): string {
  return `${designTokens.status.badgeBase} ${designTokens.status.badge[normalizedStatus(tone)]}`;
}
