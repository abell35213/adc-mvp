"use client";
import Link from "next/link";
import type { MeResponse } from "@/lib/api";
import { Button, Breadcrumbs } from "@/components/ui";
import { MobileNavigation } from "./MobileNavigation";
import { UserMenu } from "./UserMenu";
import type { ShellVariant } from "./navigation";

const LABELS: Record<string,string>={admin:"Administration",dashboard:"Command Center",incidents:"Cases",exports:"Exports",vehicles:"Vehicles",reports:"Reports",timeline:"Evidence",help:"Help",settings:"Settings",onboarding:"Onboarding",ops:"Operations"};
function titleCase(s:string){return LABELS[s]??s.replace(/-/g," ").replace(/\b\w/g,c=>c.toUpperCase())}
function crumbs(pathname:string){const parts=pathname.split("/").filter(Boolean); return parts.map((p,i)=>{const href=`/${parts.slice(0,i+1).join("/")}`; const isId=/^[a-f0-9-]{8,}$/i.test(p); return {href,label:isId?"Case detail":titleCase(p),current:i===parts.length-1};});}
export function TopBar({ title, user, pathname, organizationName, variant="default" }: { title?: string; user: MeResponse; pathname: string; organizationName: string; variant?: ShellVariant }) {
 const items=crumbs(pathname); const displayTitle=title ?? items.at(-1)?.label ?? "Command Center";
 return <header className="sticky top-0 z-20 border-b border-border-default bg-surface/95 px-4 py-3 backdrop-blur sm:px-6"><div className="flex min-w-0 items-center justify-between gap-3"><div className="flex min-w-0 items-center gap-2"><MobileNavigation user={user} pathname={pathname} organizationName={organizationName} variant={variant}/><div className="min-w-0"><Breadcrumbs items={items.length?items:[{label:"Command Center",href:"/dashboard",current:true}]}/><p className="mt-0.5 truncate text-lg font-semibold text-text-primary">{displayTitle}</p></div></div><div className="flex shrink-0 items-center gap-2"><Link href="/help" className="hidden rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-action-primary md:inline-flex">Help</Link><Link href="/incidents?quick=create"><Button size="sm">Create Incident</Button></Link><UserMenu user={user} organizationName={organizationName}/></div></div></header>;
}
