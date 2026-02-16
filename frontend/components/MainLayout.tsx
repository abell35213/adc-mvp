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

/**
 * Main layout component for the customer‑facing dashboard. It renders a top
 * navigation bar with links to the primary sections of the app (dashboard,
 * incidents, exports, vehicles) and provides a sign‑out button. The active
 * route is highlighted based on the current pathname. Additional links for
 * administrators (e.g., vehicles) are conditionally displayed when the
 * logged‑in user has the admin role.
 */
export default function MainLayout({ title, children }: MainLayoutProps) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

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

  // Define the navigation items. Vehicles is admin‑only.
  const navItems = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/incidents", label: "Incidents" },
    { href: "/exports", label: "Exports", hidden: false },
    { href: "/vehicles", label: "Vehicles", hidden: user.role !== "admin" },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="flex flex-wrap items-center justify-between border-b bg-white px-6 py-4 dark:bg-gray-800">
        <div>
          {title ? (
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">
              {title}
            </h1>
          ) : (
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">
              ADC Dashboard
            </h1>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm">
          {user.role === "admin" && (
            <Link
              href="/admin/driver-protocol"
              className="font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              Admin
            </Link>
          )}
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400"
          >
            Sign out
          </button>
        </div>
      </header>

      <nav className="border-b bg-white px-6 py-3 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex flex-wrap gap-4 text-sm">
          {navItems.map((item) => {
            if (item.hidden) return null;
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
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

      <main className="mx-auto max-w-7xl p-6">
        {children}
      </main>
    </div>
  );
}