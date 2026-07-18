"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/useAuth";
import { designTokens } from "@/lib/design/tokens";
import { hasRoleCapability } from "@/lib/permissions";
import { getOrganizationLabel, type ShellVariant } from "./navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { PageContainer } from "./PageContainer";

export function AppShell({
  title,
  children,
  variant = "default",
}: {
  title?: string;
  children: ReactNode;
  variant?: ShellVariant;
}) {
  const { user, loading } = useAuth();
  const pathname = usePathname() ?? "/";

  if (loading) return <div className="min-h-screen bg-page p-6 text-text-muted"><div className="rounded-lg border border-border-default bg-surface p-6 shadow-bordered"><p className="text-lg font-semibold text-text-primary">Loading secure workspace…</p><p className="mt-2 text-sm text-text-secondary">Validating your session before loading protected case data.</p></div></div>;

  if (!user) {
    return (
      <div className="space-y-2 p-6 text-sm text-text-muted">
        <p>You must be logged in to view this page.</p>
        <Link href="/login" className={`font-medium ${designTokens.accent.text}`}>
          Sign in
        </Link>
      </div>
    );
  }

  if (variant === "admin" && !hasRoleCapability(user.role, "vehicle_qr:read")) {
    return <div className="p-6 text-sm text-text-muted">Admin access required.</div>;
  }

  const organizationName = getOrganizationLabel(user.org_ids);
  const wide = pathname.startsWith("/dashboard") || pathname.startsWith("/incidents") || pathname.startsWith("/exports");

  return (
    <div className="min-h-screen bg-page text-text-primary">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-text-primary focus:shadow-overlay"
      >
        Skip to main content
      </a>
      <div className="flex min-h-screen">
        <Sidebar user={user} pathname={pathname} organizationName={organizationName} variant={variant} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar title={title} user={user} pathname={pathname} organizationName={organizationName} variant={variant} />
          <PageContainer wide={wide}>{children}</PageContainer>
        </div>
      </div>
    </div>
  );
}
