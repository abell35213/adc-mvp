"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const fleetSizes = ["1 – 5", "6 – 29", "30 – 499", "500 – 4,999", "5,000+"];

const bulletFeatures = [
  {
    title: "Incident-triggered evidence capture",
    body: "Auto-pull Samsara clips and combine driver uploads into one defensible incident record.",
  },
  {
    title: "Verifiable chain-of-custody",
    body: "Track every handoff with timestamped actions and integrity hashes that prove files were not altered.",
  },
  {
    title: "Litigation-ready exports",
    body: "Generate insurer and legal packages with evidence indexes, metadata, and audit trails in minutes.",
  },
];

export function Hero() {
  const [selectedFleet, setSelectedFleet] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      return;
    }

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) {
          localStorage.removeItem("token");
          setIsAuthenticated(false);
          return;
        }
        setIsAuthenticated(true);
      })
      .catch(() => {
        setIsAuthenticated(false);
      });
  }, []);

  return (
    <header className="bg-[#EBF2FA]">
      {/* ── Navbar ── */}
      <MarketingContainer>
        <nav className="flex items-center justify-between py-5" aria-label="Primary">
          <span className="text-lg font-bold tracking-tight text-[#062040]">ADC</span>

          <ul className="hidden items-center gap-8 text-sm font-medium text-[#062040] md:flex" role="list">
            <li><a className="hover:text-[#1B6EF3] transition" href="#features">Product</a></li>
            <li><a className="hover:text-[#1B6EF3] transition" href="#solutions">Solutions</a></li>
            <li><a className="hover:text-[#1B6EF3] transition" href="#pricing">Pricing</a></li>
            <li><a className="hover:text-[#1B6EF3] transition" href="#resources">Resources</a></li>
          </ul>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link href="/dashboard" className={marketingTokens.buttonVariants.ghost}>
                Go to dashboard
              </Link>
            ) : (
              <Link href="/login" className={marketingTokens.buttonVariants.ghost}>
                Sign in
              </Link>
            )}
            <div className="h-5 w-px bg-slate-300" aria-hidden="true" />
            <Link href="/pricing" className={marketingTokens.buttonVariants.secondary}>
              Check Our Prices
            </Link>
            <Link href="/company/contact" className={marketingTokens.buttonVariants.primary}>
              Try the Demo
            </Link>
          </div>
        </nav>
      </MarketingContainer>

      {/* ── Hero split ── */}
      <MarketingContainer>
        <div className="grid gap-12 pb-20 pt-12 lg:grid-cols-[1.2fr_1fr] lg:items-start">
          {/* Left column */}
          <div className="space-y-7">
            {/* Rating badge */}
            <div className="flex items-center gap-2 text-sm text-[#062040]">
              <span className="text-red-500 text-base leading-none" aria-hidden="true">★★★★½</span>
              <span className="sr-only">4.5 out of 5 stars.</span>
              <span className="font-medium">G2 4.5 stars &nbsp;·&nbsp; 2,900+ reviews</span>
            </div>

            <h1 className={marketingTokens.headingScale.display}>
              Defend Every Claim With Verifiable Evidence
            </h1>

            <p className="text-lg leading-8 text-slate-600 max-w-lg">
              When an incident happens, ADC assembles proof fast—capturing telematics and media, preserving integrity, and packaging evidence for insurers and counsel.
            </p>

            <ul className="space-y-4" aria-label="Key capabilities">
              {bulletFeatures.map(({ title, body }) => (
                <li key={title} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#062040] text-white text-[10px]" aria-hidden="true">
                    ✓
                  </span>
                  <span className="text-slate-700 text-sm leading-6">
                    <strong className="font-semibold text-[#062040]">{title}</strong>
                    {" "}–{" "}{body}
                  </span>
                </li>
              ))}
            </ul>

            {/* Logo strip */}
            <div className="pt-6 border-t border-slate-200/80">
              <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Trusted by leading fleet operators
              </p>
              <ul className="flex flex-wrap items-center gap-x-8 gap-y-3" role="list" aria-label="Customer logos">
                {["NorthLine Freight", "Summit Logistics", "Apex Transport"].map((name) => (
                  <li key={name} className="text-sm font-bold text-slate-400 uppercase tracking-wide">
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Right column — pricing form card */}
          <div className="rounded-2xl bg-white p-8 shadow-lg border border-slate-200">
            <h2 className="text-xl font-bold text-[#062040] mb-6 text-center">
              Get pricing in minutes
            </h2>

            <form aria-label="Get pricing form" className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="sr-only" htmlFor="first-name">First name</label>
                  <input
                    id="first-name"
                    name="firstName"
                    type="text"
                    required
                    placeholder="First name"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                  />
                </div>
                <div>
                  <label className="sr-only" htmlFor="last-name">Last name</label>
                  <input
                    id="last-name"
                    name="lastName"
                    type="text"
                    required
                    placeholder="Last name"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                  />
                </div>
              </div>

              <div>
                <label className="sr-only" htmlFor="company">Company name</label>
                <input
                  id="company"
                  name="company"
                  type="text"
                  required
                  placeholder="Company name"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="sr-only" htmlFor="email">Email address</label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    placeholder="Email address"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                  />
                </div>
                <div>
                  <label className="sr-only" htmlFor="phone">Phone number</label>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    placeholder="Phone number"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                  />
                </div>
              </div>

              <fieldset>
                <legend className="mb-3 text-sm font-medium text-[#062040]">
                  How many vehicles are in your fleet?
                </legend>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Fleet size">
                  {fleetSizes.map((size) => (
                    <button
                      key={size}
                      type="button"
                      onClick={() => setSelectedFleet(size)}
                      aria-pressed={selectedFleet === size}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] ${
                        selectedFleet === size
                          ? "border-[#062040] bg-[#062040] text-white"
                          : "border-slate-300 bg-white text-slate-600 hover:border-[#062040] hover:text-[#062040]"
                      }`}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </fieldset>

              <button
                type="submit"
                className="w-full rounded-full bg-[#1B6EF3] py-3.5 text-sm font-bold text-white transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] focus-visible:ring-offset-2"
              >
                Check Our Prices
              </button>
            </form>

            <p className="mt-4 text-center text-xs text-slate-400 leading-relaxed">
              By submitting this form you agree to ADC&apos;s{" "}
              <a href="/terms" className="underline hover:text-slate-600">terms of service</a>
              {" "}and{" "}
              <a href="/privacy" className="underline hover:text-slate-600">privacy policy</a>.
            </p>
          </div>
        </div>
      </MarketingContainer>
    </header>
  );
}
