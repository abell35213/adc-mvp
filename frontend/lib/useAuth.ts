"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, type MeResponse } from "@/lib/api";

/**
 * Hook that validates the current session by calling /auth/me.
 * Redirects to /login when the server-side session is missing or invalid.
 */
export function useAuth() {
  const router = useRouter();
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  return { user, loading };
}
