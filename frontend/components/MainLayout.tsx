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
  area: "Operations" | "Evidence" | "Exports" | "Administration";
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
  "driver-protocol": "Driver Protocol",
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
        { href: "/onboarding", label: "Onboarding", hidden: !canViewOnboarding },
        { href: "/incidents", label: "Incidents", activePrefixes: ["/incidents"] },
        { href: "/timeline", label: "Timeline" },
      ],
    },
    {
      area: "Evidence",
      items: [{ href: "/vehicles", label: "Vehicles", hidden: !canManageQr }],
    },
    {
      area: "Exports",
      items: [{ href: "/exports", label: "Exports", activePrefixes: ["/exports"] }],
    },
    {
      area: "Administration",
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

  return (
    <div className="min-h-screen bg-page text-text-primary">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-default bg-shell px-6 py-4 text-text-inverse">
        <div>
          <Link href={defaultLanding} className="inline-block">
            <h1 className="text-lg font-bold text-text-inverse hover:text-accent-soft">
              {title ?? "ADC Dashboard"}
            </h1>
          </Link>
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
          <button
            onClick={logout}
            className="ml-1 text-sm text-accent-soft hover:text-text-inverse"
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="space-y-3 border-b border-border-default bg-shell/95 px-6 py-3 text-text-inverse">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {navGroups.map((group) => {
            const visibleItems = group.items.filter((item) => !item.hidden);
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.area}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-accent-soft">
                  {group.area}
                </p>
                <div className="flex flex-wrap gap-2 text-sm">
                  {visibleItems.map((item) => {
                    const isActive = routeIsActive(pathname, item.href, item.activePrefixes);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`rounded-full px-3 py-1 transition ${
                          isActive
                            ? "bg-accent text-text-inverse"
                            : "text-accent-soft hover:bg-surface/10"
                        }`}
                        aria-current={isActive ? "page" : undefined}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {breadcrumbs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 text-xs text-accent-soft">
            <Link href={defaultLanding} className="hover:text-text-inverse">
              Home
            </Link>
            {breadcrumbs.map((crumb, idx) => {
              const last = idx === breadcrumbs.length - 1;
              return (
                <span key={crumb.href} className="flex items-center gap-1">
                  <span>/</span>
                  {last ? (
                    <span className="font-medium text-text-inverse">{crumb.label}</span>
                  ) : (
                    <Link href={crumb.href} className="hover:text-text-inverse">
                      {crumb.label}
                    </Link>
                  )}
                </span>
              );
            })}
          </div>
        )}
      </nav>

      <main className="mx-auto max-w-7xl p-6">{children}</main>
    </div>
  );
}
