"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { marketingTokens } from "@/components/marketing/tokens";

const fleetSizes = ["1 – 5", "6 – 29", "30 – 499", "500 – 4,999", "5,000+"];

const primaryNavLinks = [
  { label: "Product", href: "/product" },
  { label: "Solutions", href: "/solutions" },
  { label: "Platform", href: "/platform" },
  { label: "Pricing", href: "/pricing" },
  { label: "Resources", href: "/resources" },
  { label: "Company", href: "/company" },
];

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
      <MarketingContainer>
        <nav className="flex items-center justify-between py-5" aria-label="Primary">
          <span className="text-lg font-bold tracking-tight text-[#062040]">ADC</span>

          <ul className="hidden items-center gap-8 text-sm font-medium text-[#062040] md:flex" role="list">
            {primaryNavLinks.map(({ label, href }) => (
              <li key={label}>
                <Link className="transition hover:text-[#1B6EF3]" href={href}>
                  {label}
                </Link>
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-3 lg:flex">
            <Link href="/resources/docs" className={marketingTokens.buttonVariants.ghost}>
              Docs
            </Link>
            <Link href="/company/contact" className={marketingTokens.buttonVariants.ghost}>
              Contact
            </Link>
            </div>
            <Link href="/company/contact" className={marketingTokens.buttonVariants.primary}>
              Book demo
            </Link>
          </div>
        </nav>
      </MarketingContainer>

      <MarketingContainer>
        <div className="grid gap-12 pb-20 pt-12 lg:grid-cols-[1.2fr_1fr] lg:items-start">
          <div className="space-y-7">
            <div className="flex items-center gap-2 text-sm text-[#062040]">
              <span className="text-base leading-none text-red-500" aria-hidden="true">★★★★½</span>
              <span className="sr-only">4.5 out of 5 stars.</span>
              <span className="font-medium">G2 4.5 stars &nbsp;·&nbsp; 2,900+ reviews</span>
            </div>

            <h1 className={marketingTokens.headingScale.display}>
              Operate Smarter<sup className="align-super text-3xl">™</sup>
            </h1>

            <p className="max-w-lg text-lg leading-8 text-slate-600">
              Lower costs and improve safety with an open, secure platform built to scale.
            </p>

            <ul className="space-y-4" aria-label="Key capabilities">
              {bulletFeatures.map(({ title, body }) => (
                <li key={title} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#062040] text-[10px] text-white" aria-hidden="true">
                    ✓
                  </span>
                  <span className="text-sm leading-6 text-slate-700">
                    <strong className="font-semibold text-[#062040]">{title}</strong>
                    {" "}– {body}
                  </span>
                </li>
              ))}
            </ul>

            <div className="border-t border-slate-200/80 pt-6">
              <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-400">
                Trusted by leading fleet operators
              </p>
              <ul className="flex flex-wrap items-center gap-x-8 gap-y-3" role="list" aria-label="Customer logos">
                {["NorthLine Freight", "Summit Logistics", "Apex Transport"].map((name) => (
                  <li key={name} className="text-sm font-bold uppercase tracking-wide text-slate-400">
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
            <h2 className="mb-6 text-center text-xl font-bold text-[#062040]">Get pricing in minutes</h2>

            <form aria-label="Get pricing form" className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="sr-only" htmlFor="first-name">First name</label>
                  <input id="first-name" name="firstName" type="text" required placeholder="First name" className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]" />
                </div>
                <div>
                  <label className="sr-only" htmlFor="last-name">Last name</label>
                  <input id="last-name" name="lastName" type="text" required placeholder="Last name" className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]" />
                </div>
              </div>

              <div>
                <label className="sr-only" htmlFor="company">Company name</label>
                <input id="company" name="company" type="text" required placeholder="Company name" className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="sr-only" htmlFor="email">Email address</label>
                  <input id="email" name="email" type="email" required placeholder="Email address" className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]" />
                </div>
                <div>
                  <label className="sr-only" htmlFor="phone">Phone number</label>
                  <input id="phone" name="phone" type="tel" placeholder="Phone number" className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-[#062040] placeholder-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]" />
                </div>
              </div>

              <fieldset>
                <legend className="mb-3 text-sm font-medium text-[#062040]">How many vehicles are in your fleet?</legend>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Fleet size">
                  {fleetSizes.map((size) => (
                    <button key={size} type="button" onClick={() => setSelectedFleet(size)} aria-pressed={selectedFleet === size} className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] ${
                      selectedFleet === size
                        ? "border-[#062040] bg-[#062040] text-white"
                        : "border-slate-300 bg-white text-slate-600 hover:border-[#062040] hover:text-[#062040]"
                    }`}>
                      {size}
                    </button>
                  ))}
                </div>
              </fieldset>

              <button type="submit" className="w-full rounded-full bg-[#1B6EF3] py-3.5 text-sm font-bold text-white transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] focus-visible:ring-offset-2">
                Check Our Prices
              </button>
            </form>

            <p className="mt-4 text-center text-xs leading-relaxed text-slate-400">
              By submitting this form you agree to ADC&apos;s <a href="/terms" className="underline hover:text-slate-600">terms of service</a>{" "}
              and <a href="/privacy" className="underline hover:text-slate-600">privacy policy</a>.
            </p>
          </div>
        </div>
      </MarketingContainer>
    </header>
  );
}
