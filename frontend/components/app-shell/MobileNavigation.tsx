"use client";
import { useState } from "react";
import Link from "next/link";
import type { MeResponse } from "@/lib/api";
import { Button, Drawer, IconButton } from "@/components/ui";
import { NavigationItem } from "./NavigationItem";
import type { ShellVariant } from "./navigation";
import { buildNavigation } from "./navigation";

export function MobileNavigation({ user, pathname, organizationName, variant = "default" }: { user: MeResponse; pathname: string; organizationName: string; variant?: ShellVariant }) {
 const [open,setOpen]=useState(false); const nav=buildNavigation(user.role, variant);
 return <><IconButton label="Open navigation menu" variant="quiet" onClick={()=>setOpen(true)} className="lg:hidden"><span aria-hidden>☰</span></IconButton><Drawer open={open} onClose={()=>setOpen(false)} title="ADC navigation" description={organizationName} side="right"><div className="space-y-5"><div><p className="text-lg font-semibold text-text-primary">ADC</p><p className="text-sm text-text-secondary">Accident Defense Center</p></div><Link href="/incidents?quick=create" onClick={()=>setOpen(false)}><Button fullWidth>Create Incident</Button></Link><nav aria-label="Mobile navigation" className="space-y-1 rounded-lg bg-[#101828] p-2">{nav.map(item=><NavigationItem key={item.href} item={item} pathname={pathname} onNavigate={()=>setOpen(false)}/>)}</nav><div className="rounded-lg border border-border-default p-3 text-sm"><p className="font-medium text-text-primary">{user.email}</p><p className="text-text-secondary">{organizationName}</p></div></div></Drawer></>;
}
