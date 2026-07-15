"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { cn } from "@/lib/design/utilities";
import { IconButton } from "./IconButton";

const FOCUSABLE = 'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';
function getFocusable(container: HTMLElement) { return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null); }
function manageDialogFocus(open: boolean, ref: React.RefObject<HTMLElement | null>, onClose: () => void) {
  if (!open) return undefined;
  const prev = document.activeElement as HTMLElement | null;
  const previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => (getFocusable(ref.current ?? document.body)[0] ?? ref.current)?.focus());
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
    if (e.key !== "Tab" || !ref.current) return;
    const focusable = getFocusable(ref.current);
    if (focusable.length === 0) { e.preventDefault(); ref.current.focus(); return; }
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  document.addEventListener("keydown", onKeyDown);
  return () => { document.removeEventListener("keydown", onKeyDown); document.body.style.overflow = previousOverflow; prev?.focus(); };
}

export function Drawer({ open, onClose, title, description, children, footer, side = "right" }: { open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; side?: "right"; }) {
  const ref = useRef<HTMLElement>(null); const id = useId(); const titleId = `drawer-${id}-title`; const descriptionId = description ? `drawer-${id}-description` : undefined;
  useEffect(() => manageDialogFocus(open, ref, onClose), [open, onClose]);
  if (!open) return null;
  return <div className="fixed inset-0 z-50 bg-black/40" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><aside ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} className={cn("absolute top-0 h-full w-full max-w-md overflow-y-auto border-border-default bg-surface shadow-overlay", side === "right" && "right-0 border-l")}><div className="flex items-start justify-between gap-3 border-b border-border-subtle p-5"><div><h2 id={titleId} className="text-lg font-semibold text-text-primary">{title}</h2>{description && <p id={descriptionId} className="mt-1 text-sm text-text-secondary">{description}</p>}</div><IconButton label="Close navigation drawer" variant="quiet" onClick={onClose}>×</IconButton></div><div className="p-5">{children}</div>{footer && <div className="border-t border-border-subtle p-5">{footer}</div>}</aside></div>;
}
