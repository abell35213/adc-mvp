/** Session utilities for httpOnly-cookie authentication. */

import { getMe } from "@/lib/api";

/**
 * Validate whether the current browser has a server-side authenticated session.
 * This relies on httpOnly cookies and never checks client-side token storage.
 */
export async function isAuthenticated(): Promise<boolean> {
  try {
    await getMe();
    return true;
  } catch {
    return false;
  }
}

/**
 * Clear any in-memory auth state.
 * Cookie clearing must be performed by the backend via /auth/logout.
 */
export function clearClientAuthState(): void {
  // Intentionally empty: no persistent client-side auth token is stored.
}
