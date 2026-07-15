"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { cn } from "@/lib/design/utilities";
import { Button } from "./Button";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  const titleId = `modal-${id}-title`;
  const descriptionId = description ? `modal-${id}-description` : undefined;

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          "w-full rounded-xl border border-border-default bg-surface shadow-overlay",
          size === "sm" ? "max-w-md" : size === "lg" ? "max-w-3xl" : "max-w-xl",
        )}
      >
        <div className="border-b border-border-subtle p-5">
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
        <div className="flex justify-end gap-2 border-t border-border-subtle p-5">
          {footer ?? (
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
