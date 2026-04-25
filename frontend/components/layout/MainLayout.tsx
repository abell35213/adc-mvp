"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { hasRoleCapability } from "@/lib/permissions";
import { designTokens } from "@/lib/design/tokens";

interface MainLayoutProps {
  title?: string;
  children: ReactNode;
}

interface NavItem {
  href: string;
  label: string;
  activePrefixes?: string[];
  hidden?: boolean;
}

interface NavGroup {
  area: "Operations" | "Deployment" | "Insights" | "Support" | "Admin";
  items: NavItem[];
}

interface QuickAction {
  href: string;
  label: string;
  ariaLabel: string;
  className: string;
}

const SEGMENT_LABELS: Record<string, string> = {
  admin: "Administration",
  incidents: "Incidents",
  exports: "Exports",
  dashboard: "Dashboard",
  vehicles: "Vehicles",
  timeline: "Timeline",
  onboarding: "Onboarding",
  "driver-protocol": "Driver Protocol",
  "plan-features": "Plan & Features",
  ops: "Ops",
};

function getDefaultLandingForRole(role: string): string {
  switch (role) {
    case "admin":
      return "/admin/driver-protocol";
    case "legal_reviewer":
      return "/exports";
    case "operator":
    case "safety_manager":
      return "/incidents";
    default:
      return "/dashboard";
  }
}

function routeIsActive(pathname: string, href: string, prefixes: string[] = []): boolean {
  const candidates = [href, ...prefixes];
  return candidates.some((candidate) => pathname === candidate || pathname.startsWith(`${candidate}/`));
}

function toTitleCase(segment: string): string {
  if (SEGMENT_LABELS[segment]) return SEGMENT_LABELS[segment];

  return segment
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function contentWidthClass(pathname: string): string {
  if (pathname.startsWith("/admin")) return "max-w-5xl";
  if (pathname.startsWith("/incidents/")) return "max-w-6xl";
  if (pathname.startsWith("/dashboard") || pathname.startsWith("/incidents")) return "max-w-7xl";
  return "max-w-6xl";
}

export default function MainLayout({ title, children }: MainLayoutProps) {
  const { user, loading } = useAuth();
  const pathname = usePathname() ?? "/";

  if (loading) {
    return <div className="p-6 text-text-muted">Loading…</div>;
  }

  if (!user) {
    return (
      <div className="space-y-2 p-6 text-sm text-text-muted">
        <p>You must be logged in to view this page.</p>
        <div className="flex items-center gap-4">
          <Link href="/login" className={`font-medium ${designTokens.accent.text}`}>
            Sign in
          </Link>
          <Link href="/" className="font-medium text-text-secondary hover:underline">
            Back to homepage
          </Link>
        </div>
      </div>
    );
  }

  const defaultLanding = getDefaultLandingForRole(user.role);
  const canViewOnboarding = hasRoleCapability(user.role, "readiness:view");
  const canManageQr = hasRoleCapability(user.role, "vehicle_qr:write");
  const canManageExports = hasRoleCapability(user.role, "onboarding:write");

  const navGroups: NavGroup[] = [
    {
      area: "Operations",
      items: [
        { href: "/dashboard", label: "Dashboard" },
        { href: "/incidents", label: "Incidents", activePrefixes: ["/incidents"] },
        { href: "/timeline", label: "Timeline" },
        { href: "/onboarding", label: "Onboarding", hidden: !canViewOnboarding },
      ],
    },
    {
      area: "Deployment",
      items: [{ href: "/vehicles", label: "Vehicles", hidden: !canManageQr }],
    },
    {
      area: "Insights",
      items: [{ href: "/exports", label: "Exports", activePrefixes: ["/exports"] }],
    },
    {
      area: "Support",
      items: [
        {
          href: "/admin/ops",
          label: "Ops Dashboard",
          activePrefixes: ["/admin/ops"],
          hidden: !hasRoleCapability(user.role, "vehicle_qr:read"),
        },
      ],
    },
    {
      area: "Admin",
      items: [
        {
          href: "/admin/driver-protocol",
          label: "Driver Protocol",
          activePrefixes: ["/admin/driver-protocol"],
          hidden: !hasRoleCapability(user.role, "onboarding:write"),
        },
        {
          href: "/admin/vehicles",
          label: "Admin Vehicles",
          activePrefixes: ["/admin/vehicles"],
          hidden: !canManageQr,
        },
        {
          href: "/admin/plan-features",
          label: "Plan & Features",
          activePrefixes: ["/admin/plan-features"],
          hidden: !hasRoleCapability(user.role, "user_management:write"),
        },
      ],
    },
  ];

  const quickActions: QuickAction[] = [
    {
      href: "/incidents?quick=create",
      label: "+ Create Incident",
      ariaLabel: "Create a new incident",
      className:
        "rounded-md border border-accent/40 bg-accent-soft/30 px-3 py-1 font-medium text-accent hover:bg-accent-soft",
    },
    {
      href: "/incidents?filter=active",
      label: "Open Active Queue",
      ariaLabel: "Open active incident queue",
      className:
        "rounded-md border border-status-warning/35 bg-status-warning-soft/60 px-3 py-1 font-medium text-status-warning hover:bg-status-warning-soft",
    },
    {
      href: "/exports?intent=request",
      label: "Request Export",
      ariaLabel: "Open export request flow",
      className:
        "rounded-md border border-status-success/35 bg-status-success-soft/60 px-3 py-1 font-medium text-status-success hover:bg-status-success-soft",
    },
  ].filter((action) => (action.label === "Request Export" ? canManageExports : true));

  const breadcrumbs = pathname
    .split("/")
    .filter(Boolean)
    .map((segment, index, all) => {
      const href = `/${all.slice(0, index + 1).join("/")}`;
      const isIdLike = /^[a-f0-9-]{8,}$/i.test(segment);
      return {
        href,
        label: isIdLike ? `${segment.slice(0, 8)}…` : toTitleCase(segment),
      };
    })
    .filter((crumb) => crumb.href !== defaultLanding);

  const visibleGroups = navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => !item.hidden) }))
    .filter((group) => group.items.length > 0);

  return (
    <div className="min-h-screen bg-page text-text-primary">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 flex-col border-r border-white/10 bg-[#0b1633] text-text-inverse lg:flex">
          <div className="border-b border-white/10 px-5 py-5">
            <Link href={defaultLanding} className="block">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-300/90">Tenant</p>
              <p className="mt-1 text-sm font-semibold text-white">ADC Operations Cloud</p>
              <p className="mt-3 text-xs text-slate-300">{user.org_ids[0] ?? "Default Organization"}</p>
            </Link>
          </div>

          <nav className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
            {visibleGroups.map((group) => (
              <div key={group.area}>
                <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                  {group.area}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const isActive = routeIsActive(pathname, item.href, item.activePrefixes);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`block rounded-md px-3 py-2 text-sm transition ${
                          isActive
                            ? "bg-accent/20 text-white ring-1 ring-accent/50"
                            : "text-slate-200 hover:bg-white/10 hover:text-white"
                        }`}
                        aria-current={isActive ? "page" : undefined}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="border-t border-white/10 px-4 py-4">
            <p className="text-xs text-slate-300">{user.email}</p>
            <p className="mt-0.5 text-xs uppercase tracking-wide text-slate-400">Role: {user.role}</p>
            <button onClick={logout} className="mt-3 text-sm font-medium text-accent-soft hover:text-white">
              Sign out
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-border-default bg-surface px-4 py-4 sm:px-6">
            <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                {breadcrumbs.length > 0 && (
                  <div className="mb-1 flex flex-wrap items-center gap-1 text-xs text-text-muted">
                    <Link href={defaultLanding} className="hover:text-text-primary">
                      Home
                    </Link>
                    {breadcrumbs.map((crumb, idx) => {
                      const last = idx === breadcrumbs.length - 1;
                      return (
                        <span key={crumb.href} className="flex items-center gap-1">
                          <span>/</span>
                          {last ? (
                            <span className="font-medium text-text-primary">{crumb.label}</span>
                          ) : (
                            <Link href={crumb.href} className="hover:text-text-primary">
                              {crumb.label}
                            </Link>
                          )}
                        </span>
                      );
                    })}
                  </div>
                )}
                <h1 className="truncate text-xl font-semibold text-text-primary">{title ?? "ADC Dashboard"}</h1>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm">
                {quickActions.map((action) => (
                  <Link
                    key={action.label}
                    href={action.href}
                    aria-label={action.ariaLabel}
                    className={action.className}
                  >
                    {action.label}
                  </Link>
                ))}
              </div>
            </div>
          </header>

          <main className={`mx-auto w-full px-4 py-6 sm:px-6 ${contentWidthClass(pathname)}`}>{children}</main>
        </div>
      </div>
    </div>
  );
}
