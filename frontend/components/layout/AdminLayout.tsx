"use client";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
export default function AdminLayout({ title, children }: { title: string; children: ReactNode }) { return <AppShell title={title} variant="admin">{children}</AppShell>; }
