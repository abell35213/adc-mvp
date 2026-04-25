"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { hasRoleCapability } from "@/lib/permissions";

interface NavItem {
  href: string;
  label: string;
  group: "Operations" | "Deployment" | "Insights" | "Support" | "Admin";
  hidden?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/admin/ops", label: "Ops Dashboard", group: "Operations" },
  { href: "/admin/ops/audit", label: "Audit Search", group: "Insights" },
  { href: "/admin/driver-protocol", label: "Driver Protocol", group: "Deployment" },
  { href: "/admin/driver-protocol/instructions", label: "Instructions", group: "Support" },
  { href: "/admin/vehicles", label: "Vehicles", group: "Deployment" },
];

type AdminLayoutProps = {
  title: string;
  children: ReactNode;
};

function toTitleCase(segment: string): string {
  return segment
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function AdminLayout({ title, children }: AdminLayoutProps) {
  const { user, loading } = useAuth();
  const pathname = usePathname() ?? "/admin";

  if (loading) {
    return <div className="p-6 text-gray-500">Loading…</div>;
  }

  if (!user || !hasRoleCapability(user.role, "vehicle_qr:read")) {
    return <div className="p-6 text-sm text-gray-500">Admin access required.</div>;
  }

  const allItems: NavItem[] = [
    ...NAV_ITEMS,
    {
      href: "/admin/plan-features",
      label: "Plan & Features",
      group: "Admin" as const,
      hidden: !hasRoleCapability(user.role, "user_management:write"),
    },
  ].filter((item) => !item.hidden);

  const groupedItems = allItems.reduce<Record<string, NavItem[]>>((acc, item) => {
    acc[item.group] = [...(acc[item.group] ?? []), item];
    return acc;
  }, {});

  const breadcrumbs = pathname
    .split("/")
    .filter(Boolean)
    .map((segment, index, all) => {
      const href = `/${all.slice(0, index + 1).join("/")}`;
      return { href, label: toTitleCase(segment) };
    });

  return (
    <div className="min-h-screen bg-page text-text-primary">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 flex-col border-r border-white/10 bg-[#0b1633] text-white lg:flex">
          <div className="border-b border-white/10 px-5 py-5">
            <Link href="/admin/ops" className="block">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-300/90">Tenant</p>
              <p className="mt-1 text-sm font-semibold">ADC Operations Cloud</p>
              <p className="mt-3 text-xs text-slate-300">{user.org_ids[0] ?? "Default Organization"}</p>
            </Link>
          </div>

          <nav className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
            {(["Operations", "Deployment", "Insights", "Support", "Admin"] as const).map((groupName) => {
              const items = groupedItems[groupName] ?? [];
              if (items.length === 0) return null;

              return (
                <div key={groupName}>
                  <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                    {groupName}
                  </p>
                  <div className="space-y-1">
                    {items.map((item) => {
                      const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
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
              );
            })}
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
            <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3">
              <div>
                <div className="mb-1 flex flex-wrap items-center gap-1 text-xs text-text-muted">
                  <Link href="/admin/ops" className="hover:text-text-primary">
                    Admin
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
                <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <Link
                  href="/admin/ops/audit"
                  className="rounded-md border border-border-default bg-surface px-3 py-1 text-text-secondary hover:bg-surface-muted"
                >
                  Audit Search
                </Link>
                <button onClick={logout} className="rounded-md px-3 py-1 text-text-secondary hover:bg-surface-muted">
                  Sign out
                </button>
              </div>
            </div>
          </header>

          <main className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
