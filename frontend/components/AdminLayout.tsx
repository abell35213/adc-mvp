"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

const NAV_ITEMS = [
  { href: "/admin/driver-protocol", label: "Driver Protocol" },
  { href: "/admin/driver-protocol/instructions", label: "Instructions" },
  { href: "/admin/vehicles", label: "Vehicles" },
  { href: "/admin/ops", label: "Ops Dashboard" },
  { href: "/admin/ops/audit", label: "Audit Search" },
];

const AUTHORIZED_OPS_ROLES = new Set([
  "admin",
  "org_admin",
  "system_admin",
  "support_admin",
  "support_agent",
]);

type AdminLayoutProps = {
  title: string;
  children: ReactNode;
};

export default function AdminLayout({ title, children }: AdminLayoutProps) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return <div className="p-6 text-gray-500">Loading…</div>;
  }

  if (!user || !AUTHORIZED_OPS_ROLES.has(user.role)) {
    return (
      <div className="p-6 text-sm text-gray-500">
        Admin access required.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b bg-white px-6 py-4 dark:bg-gray-800">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">Admin</p>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h1>
        </div>
        <button
          onClick={logout}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400"
        >
          Sign out
        </button>
      </header>

      <nav className="border-b bg-white px-6 py-3 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex flex-wrap gap-4 text-sm">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-3 py-1 transition ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <main className="mx-auto max-w-5xl p-6">{children}</main>
    </div>
  );
}
