"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { cn } from "@/lib/design/utilities";

export function Drawer({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  side = "right",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  side?: "right";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  const titleId = `drawer-${id}-title`;
  const descriptionId = description ? `drawer-${id}-description` : undefined;

  useEffect(() => {
    if (!open) return;

    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      prev?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <aside
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          "absolute top-0 h-full w-full max-w-md overflow-y-auto border-border-default bg-surface shadow-overlay",
          side === "right" && "right-0 border-l",
        )}
      >
        <div className="border-b border-border-subtle p-5">
          <button onClick={onClose} aria-label="Close drawer" className="float-right text-text-muted hover:text-text-primary">
            ×
          </button>
          <h2 id={titleId} className="text-lg font-semibold text-text-primary">
            {title}
          </h2>
          {description && (
            <p id={descriptionId} className="mt-1 text-sm text-text-secondary">
              {description}
            </p>
          )}
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="border-t border-border-subtle p-5">{footer}</div>}
      </aside>
    </div>
  );
}
