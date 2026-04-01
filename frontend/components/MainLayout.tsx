"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

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
    return <div className="p-6 text-gray-500">Loading…</div>;
  }

  if (!user) {
    return (
      <div className="p-6 text-sm text-gray-500">
        You must be logged in to view this page.
      </div>
    );
  }

  const defaultLanding = getDefaultLandingForRole(user.role);

  const navGroups: NavGroup[] = [
    {
      area: "Operations",
      items: [
        { href: "/dashboard", label: "Dashboard" },
        { href: "/incidents", label: "Incidents", activePrefixes: ["/incidents"] },
        { href: "/timeline", label: "Timeline" },
      ],
    },
    {
      area: "Evidence",
      items: [{ href: "/vehicles", label: "Vehicles", hidden: user.role !== "admin" }],
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
          hidden: user.role !== "admin",
        },
        {
          href: "/admin/vehicles",
          label: "Admin Vehicles",
          activePrefixes: ["/admin/vehicles"],
          hidden: user.role !== "admin",
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
        "rounded border border-blue-200 px-3 py-1 font-medium text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300 dark:hover:bg-blue-950",
    },
    {
      href: "/incidents?filter=active",
      label: "Open Active Queue",
      ariaLabel: "Open active incident queue",
      className:
        "rounded border border-amber-200 px-3 py-1 font-medium text-amber-700 hover:bg-amber-50 dark:border-amber-700 dark:text-amber-300 dark:hover:bg-amber-950",
    },
    {
      href: "/exports?intent=request",
      label: "Request Export",
      ariaLabel: "Open export request flow",
      className:
        "rounded border border-emerald-200 px-3 py-1 font-medium text-emerald-700 hover:bg-emerald-50 dark:border-emerald-700 dark:text-emerald-300 dark:hover:bg-emerald-950",
    },
  ];

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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white px-6 py-4 dark:bg-gray-800">
        <div>
          <Link href={defaultLanding} className="inline-block">
            <h1 className="text-lg font-bold text-gray-900 hover:text-blue-700 dark:text-white dark:hover:text-blue-300">
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
            className="ml-1 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400"
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="space-y-3 border-b bg-white px-6 py-3 dark:border-gray-700 dark:bg-gray-800">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {navGroups.map((group) => {
            const visibleItems = group.items.filter((item) => !item.hidden);
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.area}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
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
                            ? "bg-blue-600 text-white"
                            : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
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
          <div className="flex flex-wrap items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
            <Link href={defaultLanding} className="hover:text-gray-700 dark:hover:text-gray-200">
              Home
            </Link>
            {breadcrumbs.map((crumb, idx) => {
              const last = idx === breadcrumbs.length - 1;
              return (
                <span key={crumb.href} className="flex items-center gap-1">
                  <span>/</span>
                  {last ? (
                    <span className="font-medium text-gray-700 dark:text-gray-200">{crumb.label}</span>
                  ) : (
                    <Link href={crumb.href} className="hover:text-gray-700 dark:hover:text-gray-200">
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
