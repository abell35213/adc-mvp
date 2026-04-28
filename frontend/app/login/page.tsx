"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "@/lib/api";

const DEMO_EMAIL_FALLBACK = "demo-admin@adc.local";
const DEMO_PASSWORD_FALLBACK = "DemoAdmin!2345";

/**
 * Login page.  Provides a simple email and password form for users to
 * authenticate.  Upon successful login the user is redirected to the
 * dashboard.  Any errors are displayed to the user.  Styling
 * matches the overall dashboard aesthetic.
 *
 * When the URL carries `?demo=1` the form is prefilled with the seeded
 * demo-tenant credentials (sourced from NEXT_PUBLIC_DEMO_EMAIL /
 * NEXT_PUBLIC_DEMO_PASSWORD, with safe local-dev fallbacks) and a
 * sandbox banner is rendered above the form.  This is the entry point
 * used by the marketing-site "Try the demo" CTAs.
 */
export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemoMode = searchParams?.get("demo") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isDemoMode) return;
    const demoEmail = process.env.NEXT_PUBLIC_DEMO_EMAIL ?? DEMO_EMAIL_FALLBACK;
    const demoPassword =
      process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? DEMO_PASSWORD_FALLBACK;
    setEmail((current) => current || demoEmail);
    setPassword((current) => current || demoPassword);
  }, [isDemoMode]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push(isDemoMode ? "/dashboard?demo=1" : "/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-lg bg-white p-8 shadow dark:bg-gray-800"
      >
        <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
          ADC Dashboard
        </h1>

        {isDemoMode && (
          <div
            role="status"
            data-testid="demo-sandbox-banner"
            className="mb-4 rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800"
          >
            <p className="font-semibold">You&apos;re entering the ADC demo sandbox.</p>
            <p className="mt-1">
              Credentials are prefilled. Data is seeded for demonstration only and
              may be reset periodically.
            </p>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded bg-red-100 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
          Email
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded border px-3 py-2 text-sm dark:bg-gray-700 dark:text-white"
        />

        <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
          Password
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-6 w-full rounded border px-3 py-2 text-sm dark:bg-gray-700 dark:text-white"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}