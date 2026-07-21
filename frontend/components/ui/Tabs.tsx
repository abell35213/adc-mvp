"use client";

import type { KeyboardEvent } from "react";
import { cn } from "@/lib/design/utilities";
import { focusRing } from "@/lib/design/variants";

export type TabItem = { id: string; label: string; disabled?: boolean };

export function Tabs({
  items,
  activeId,
  onChange,
  label = "Section tabs",
}: {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  label?: string;
}) {
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const enabled = items.filter((item) => !item.disabled);
    if (enabled.length === 0) return;

    const idx = enabled.findIndex((item) => item.id === activeId);
    const currentIndex = idx === -1 ? 0 : idx;

    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 1 : -1;
      const next = enabled[(currentIndex + delta + enabled.length) % enabled.length];
      onChange(next.id);
    }
  }

  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex gap-1 border-b border-border-subtle">
      {items.map((item) => (
        <button
          key={item.id}
          role="tab"
          aria-selected={item.id === activeId}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
          className={cn(
            "-mb-px cursor-pointer border-b-2 px-3 py-2 text-sm font-medium",
            focusRing,
            item.id === activeId
              ? "border-action-primary text-text-primary"
              : "border-transparent text-text-secondary hover:text-text-primary",
            item.disabled && "cursor-not-allowed opacity-50",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function SegmentedControl({
  items,
  activeId,
  onChange,
  label = "View options",
}: {
  items: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  label?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-border-default bg-surface p-1">
      {items.map((item) => (
        <button
          key={item.id}
          role="radio"
          aria-checked={item.id === activeId}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
          className={cn(
            "cursor-pointer rounded px-3 py-1.5 text-sm",
            focusRing,
            item.id === activeId ? "bg-action-primary text-text-inverse" : "text-text-secondary hover:bg-surface-subtle",
            item.disabled && "cursor-not-allowed opacity-50",
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
