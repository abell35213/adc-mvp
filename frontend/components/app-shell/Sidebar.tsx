"use client";
import Link from "next/link";
import type { MeResponse } from "@/lib/api";
import { NavigationItem } from "./NavigationItem";
import type { ShellVariant } from "./navigation";
import { buildNavigation, getDefaultLandingForRole } from "./navigation";

export function Sidebar({ user, pathname, organizationName, variant = "default" }: { user: MeResponse; pathname: string; organizationName: string; variant?: ShellVariant }) {
 const nav = buildNavigation(user.role, variant);
 const primary = nav.filter(i=>i.section === "primary"); const secondary = nav.filter(i=>i.section === "secondary");
 return <aside className="hidden w-64 shrink-0 flex-col border-r border-white/10 bg-[#101828] text-white lg:flex">
  <div className="border-b border-white/10 px-5 py-5"><Link href={getDefaultLandingForRole(user.role)} className="block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-action-primary focus-visible:ring-offset-2 focus-visible:ring-offset-[#101828]"><p className="text-lg font-semibold tracking-tight">ADC</p><p className="text-xs text-slate-300">Accident Defense Center</p><p className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-400">Organization</p><p className="mt-1 truncate text-sm text-slate-100">{organizationName}</p></Link></div>
  <nav aria-label="Primary navigation" className="flex-1 overflow-y-auto px-3 py-4"><div className="space-y-1">{primary.map(item=><NavigationItem key={item.href} item={item} pathname={pathname}/>)}</div></nav>
  <nav aria-label="Secondary navigation" className="border-t border-white/10 px-3 py-4"><div className="space-y-1">{secondary.map(item=><NavigationItem key={item.href} item={item} pathname={pathname}/>)}</div></nav>
  <div className="border-t border-white/10 px-5 py-4"><p className="truncate text-xs text-slate-300">{user.email}</p><p className="mt-0.5 text-xs capitalize text-slate-400">{user.role.replace(/_/g," ")}</p></div>
 </aside>;
}
