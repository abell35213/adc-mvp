"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert, Button, Card, CardContent, FormField, Input } from "@/components/ui";
import { login } from "@/lib/api";

const DEMO_EMAIL_ENV = process.env.NEXT_PUBLIC_DEMO_EMAIL;
const DEMO_PASSWORD_ENV = process.env.NEXT_PUBLIC_DEMO_PASSWORD;
const DEMO_PREFILL_ENABLED = process.env.NODE_ENV !== "production" && Boolean(DEMO_EMAIL_ENV) && Boolean(DEMO_PASSWORD_ENV);

export default function LoginPage() { return <Suspense fallback={null}><LoginPageInner /></Suspense>; }

function safeAuthMessage(error: unknown) {
  if (!(error instanceof Error)) return "We could not sign you in. Check your email and password and try again.";
  if (/401|403|invalid|unauthorized/i.test(error.message)) return "The email or password did not match an ADC account.";
  return "We could not sign you in. Please try again.";
}

function LoginPageInner() {
  const router = useRouter(); const searchParams = useSearchParams();
  const isDemoRequest = searchParams?.get("demo") === "1"; const isDemoMode = isDemoRequest && DEMO_PREFILL_ENABLED;
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState(""); const [loading,setLoading]=useState(false); const [showPassword,setShowPassword]=useState(false);
  useEffect(()=>{ if (!isDemoMode) return; setEmail((current)=>current || (DEMO_EMAIL_ENV as string)); setPassword((current)=>current || (DEMO_PASSWORD_ENV as string)); },[isDemoMode]);
  async function handleSubmit(e: FormEvent) { e.preventDefault(); setError(""); setLoading(true); try { await login(email,password); router.push(isDemoMode?"/dashboard?demo=1":"/dashboard"); } catch(err) { setError(safeAuthMessage(err)); } finally { setLoading(false); } }
  return <main className="min-h-screen bg-page px-4 py-8 text-text-primary sm:px-6"><div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center justify-center"><div className="grid w-full gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-center"><section className="hidden lg:block"><p className="text-sm font-semibold uppercase tracking-[0.16em] text-action-primary">Accident Defense Center</p><h1 className="mt-4 text-4xl font-semibold tracking-tight text-text-primary">ADC</h1><p className="mt-4 max-w-md text-lg text-text-secondary">Organize incident evidence, resolve case blockers, and prepare defense-ready records.</p><div className="mt-8 rounded-xl border border-border-default bg-surface p-5 shadow-bordered"><p className="text-sm font-semibold text-text-primary">Operational workspace</p><p className="mt-2 text-sm text-text-secondary">A calm case command center for commercial vehicle incident response teams.</p></div></section><Card className="w-full"><CardContent className="p-6 sm:p-8"><div className="mb-6"><p className="text-sm font-semibold uppercase tracking-[0.14em] text-action-primary">ADC</p><h2 className="mt-2 text-2xl font-semibold tracking-tight text-text-primary">Sign in to Accident Defense Center</h2><p className="mt-2 text-sm text-text-secondary">Use your organization credentials to continue.</p></div>{isDemoMode && (
              <div data-testid="demo-sandbox-banner" className="mb-5">
                <Alert tone="informational" title="Explore the ADC Demo" description={<span>Review a prepared commercial vehicle incident, identify missing evidence, and see how ADC organizes defense-ready case materials. Select <strong>Enter Demo Workspace</strong> to use the prefilled local demo sandbox account.</span>} />
              </div>
            )}{error && <Alert tone="critical" title="Sign-in failed" description={error} className="mb-5" />}<form onSubmit={handleSubmit} className="space-y-4"><FormField id="email" label="Email" required><Input autoFocus type="email" autoComplete="email" value={email} onChange={(e)=>setEmail(e.target.value)} /></FormField><FormField id="password" label="Password" required><div className="relative"><Input type={showPassword?"text":"password"} autoComplete="current-password" value={password} onChange={(e)=>setPassword(e.target.value)} className="pr-24"/><button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-medium text-text-secondary hover:bg-surface-subtle focus-visible:ring-2 focus-visible:ring-action-primary">{showPassword?"Hide":"Show"}</button></div></FormField><Button type="submit" fullWidth loading={loading} loadingLabel="Signing in" disabled={!email || !password}>{isDemoMode?"Enter Demo Workspace":"Sign in"}</Button></form></CardContent></Card></div></div></main>;
}
