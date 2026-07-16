"use client";
import { useEffect, useRef, useState } from "react";
import { logout, type MeResponse } from "@/lib/api";
import { Avatar } from "@/components/ui";

export function UserMenu({ user, organizationName }: { user: MeResponse; organizationName: string }) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); buttonRef.current?.focus(); }
      if (event.key === "ArrowDown") { event.preventDefault(); menuRef.current?.querySelector<HTMLButtonElement | HTMLAnchorElement>("button,a")?.focus(); }
    };
    const onPointer = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node) && !buttonRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey); document.addEventListener("mousedown", onPointer);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onPointer); };
  }, [open]);
  return <div className="relative">
    <button ref={buttonRef} type="button" aria-haspopup="menu" aria-expanded={open} aria-label={`Open account menu for ${user.email}`} onClick={() => setOpen(v => !v)} className="inline-flex items-center gap-2 rounded-md border border-border-default bg-surface px-2 py-1.5 text-sm text-text-secondary shadow-bordered outline-none hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-action-primary focus-visible:ring-offset-2">
      <Avatar name={user.email} size="sm"/><span className="hidden max-w-36 truncate md:inline">{user.email}</span>
    </button>
    {open && <div ref={menuRef} role="menu" aria-label="Account menu" className="absolute right-0 z-30 mt-2 w-72 rounded-lg border border-border-default bg-surface p-2 shadow-overlay">
      <div className="border-b border-border-subtle px-3 py-2"><p className="truncate text-sm font-semibold text-text-primary">{user.email}</p><p className="mt-1 text-xs text-text-secondary">{organizationName}</p><p className="mt-1 text-xs capitalize text-text-muted">{user.role.replace(/_/g, " ")}</p></div>
      <a role="menuitem" href="/help" className="block rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-surface-subtle focus:bg-surface-subtle focus:outline-none">Help</a>
      <button role="menuitem" onClick={() => void logout()} className="block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-action-destructive hover:bg-status-critical-soft focus:bg-status-critical-soft focus:outline-none">Sign out</button>
    </div>}
  </div>;
}
