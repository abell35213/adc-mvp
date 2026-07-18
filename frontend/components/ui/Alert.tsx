import type { ElementType, HTMLAttributes, ReactNode } from "react";

import { StatusBadge } from "./StatusBadge";
import type { StatusTone } from "@/lib/design/tokens";
import { cn } from "@/lib/design/utilities";

type AlertTitleElement = "div" | "span" | "p" | "h2" | "h3" | "h4";

export function Alert({
  tone = "informational",
  title,
  titleAs: TitleElement = "div",
  description,
  action,
  onDismiss,
  className,
  "aria-label": dismissAriaLabel,
  ...props
}: {
  tone?: Exclude<StatusTone, "neutral" | "info"> | "informational";
  title: ReactNode;
  titleAs?: AlertTitleElement;
  description?: ReactNode;
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
  "aria-label"?: string;
} & Omit<HTMLAttributes<HTMLDivElement>, "title" | "aria-label">) {
  const Title = TitleElement as ElementType;
  return (
    <div role={tone === "critical" ? "alert" : "status"} className={cn("rounded-lg border border-border-default bg-surface p-4", className)} {...props}>
      <div className="flex gap-3">
        <StatusBadge tone={tone} dot>
          {tone}
        </StatusBadge>
        <div className="min-w-0 flex-1">
          <Title className="text-sm font-semibold text-text-primary">{title}</Title>
          {description ? <div className="mt-1 text-sm text-text-secondary">{description}</div> : null}
          {action ? <div className="mt-3">{action}</div> : null}
        </div>
        {onDismiss ? (
          <button
            type="button"
            className="text-sm text-text-muted hover:text-text-primary"
            onClick={onDismiss}
            aria-label={dismissAriaLabel ?? "Dismiss alert"}
          >
            ×
          </button>
        ) : null}
      </div>
    </div>
  );
}
