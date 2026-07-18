"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe, type MeResponse } from "@/lib/api";

interface AuthContextValue {
  user: MeResponse | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function isPublicPath(pathname: string): boolean {
  return (
    pathname === "/login" ||
    pathname === "/" ||
    pathname.startsWith("/company") ||
    pathname.startsWith("/api")
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const [sessionUser, setSessionUser] = useState<MeResponse | null>(null);

  const publicPath = isPublicPath(pathname);

  useEffect(() => {
    // Skip fetch on public paths or when session is already established.
    if (publicPath || sessionUser) {
      return;
    }

    let active = true;
    getMe()
      .then((session) => {
        if (active) setSessionUser(session);
      })
      .catch(() => {
        if (active) {
          setSessionUser(null);
          router.replace("/login");
        }
      });
    return () => {
      active = false;
    };
  }, [pathname, router, sessionUser, publicPath]);

  // Derive user and loading from session state — no synchronous setState in effect needed.
  const user = publicPath ? null : sessionUser;
  const loading = !publicPath && !sessionUser;
  const value = useMemo(() => ({ user, loading }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
