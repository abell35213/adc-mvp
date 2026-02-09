/** Token handling utilities for authentication. */

const TOKEN_KEY = "token";

/** Store a JWT token in localStorage. */
export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

/** Retrieve the stored JWT token, or null if absent. */
export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

/** Remove the stored JWT token. */
export function clearToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

/** Check whether a token is currently stored. */
export function isAuthenticated(): boolean {
  return getToken() !== null;
}
