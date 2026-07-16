"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { cn } from "@/lib/design/utilities";
import { Button } from "./Button";

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

export function Modal({ open, onClose, title, description, children, footer, size = "md" }: { open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; size?: "sm" | "md" | "lg"; }) {
  const ref = useRef<HTMLDivElement>(null); const id = useId(); const titleId = `modal-${id}-title`; const descriptionId = description ? `modal-${id}-description` : undefined;
  useEffect(() => manageDialogFocus(open, ref, onClose), [open, onClose]);
  if (!open) return null;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} className={cn("max-h-[calc(100vh-2rem)] w-full overflow-y-auto rounded-xl border border-border-default bg-surface shadow-overlay", size === "sm" ? "max-w-md" : size === "lg" ? "max-w-3xl" : "max-w-xl")}><div className="border-b border-border-subtle p-5"><h2 id={titleId} className="text-lg font-semibold text-text-primary">{title}</h2>{description && <p id={descriptionId} className="mt-1 text-sm text-text-secondary">{description}</p>}</div><div className="p-5">{children}</div><div className="flex justify-end gap-2 border-t border-border-subtle p-5">{footer ?? <Button variant="secondary" onClick={onClose}>Close</Button>}</div></div></div>;
}
