"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { cn } from "@/lib/design/utilities";
import type { ShellNavItem } from "./navigation";
import { routeIsActive } from "./navigation";

function NavIcon({ name }: { name: ShellNavItem["icon"] }) {
  const common = { className: "size-4", fill: "none", stroke: "currentColor", strokeWidth: 1.8, viewBox: "0 0 24 24", "aria-hidden": true };
  const paths: Record<ShellNavItem["icon"], ReactNode> = {
    command: <><path d="M4 5h16M4 12h10M4 19h7"/><path d="M17 14l3 3-3 3"/></>,
    cases: <><path d="M6 7h12v13H6z"/><path d="M9 7V4h6v3"/></>,
    evidence: <><path d="M12 3v18M5 8h14M7 16h10"/><path d="M8 8l-3 6h6zM16 8l-3 6h6z"/></>,
    exports: <><path d="M12 4v10"/><path d="M8 10l4 4 4-4"/><path d="M5 18h14"/></>,
    vehicles: <><path d="M5 16l1.5-5h11L19 16"/><path d="M7 16h10"/><circle cx="8" cy="18" r="1.5"/><circle cx="16" cy="18" r="1.5"/></>,
    reports: <><path d="M5 19V5h14v14z"/><path d="M9 16V9M12 16v-4M15 16V7"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.7 2.7 0 1 1 4.5 2c-.9.7-1.4 1.1-1.4 2.2"/><path d="M12 17h.01"/></>,
    admin: <><path d="M12 3l7 3v5c0 4.5-2.8 8-7 10-4.2-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/></>,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

export function NavigationItem({ item, pathname, onNavigate }: { item: ShellNavItem; pathname: string; onNavigate?: () => void }) {
  const active = routeIsActive(pathname, item.href, item.activePrefixes);
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-action-primary focus-visible:ring-offset-2 focus-visible:ring-offset-[#101828]",
        active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/7 hover:text-white",
      )}
    >
      <span className={cn("absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full", active ? "bg-action-primary" : "bg-transparent")} aria-hidden />
      <NavIcon name={item.icon} />
      <span>{item.label}</span>
    </Link>
  );
}
