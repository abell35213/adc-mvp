"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getMe } from "@/lib/api";

/**
 * Root page.  Performs a simple auth check and redirects users to the
 * appropriate page based on their authentication state.  Unauthenticated
 * users are sent to the login screen while authenticated users land
 * on the dashboard.  A minimal message is displayed during the
 * redirect process.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      router.replace("/login");
      return;
    }
    getMe()
      .then(() => router.replace("/dashboard"))
      .catch(() => {
        localStorage.removeItem("token");
        router.replace("/login");
      });
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-gray-500">Redirecting…</p>
    </div>
  );
}