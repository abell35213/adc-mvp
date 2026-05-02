"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { Logo } from "@/components/marketing/Logo";
import { marketingTokens } from "@/components/marketing/tokens";
import { trackCtaClick } from "@/lib/tracking";

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
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    trackCtaClick({
      event: "lead_form_submit",
      location: "home-hero",
      label: "Request walkthrough",
    });
  };

  return (
    <header className="bg-[#EBF2FA]">
      <MarketingContainer>
        <nav className="flex items-center justify-between py-5" aria-label="Primary">
          <Link href="/" aria-label="ADC home" className="inline-flex items-center">
            <Logo variant="mark" height={36} priority />
            <span className="ml-2 text-lg font-bold tracking-tight text-[#062040]">ADC</span>
          </Link>

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
            <Link href="/login" className={marketingTokens.buttonVariants.ghost}>
              Login
            </Link>
            <Link
              href="/login?demo=1"
              className={marketingTokens.buttonVariants.secondary}
              data-testid="hero-try-demo"
            >
              Try the demo
            </Link>
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

          </div>

          <form
            className={`${marketingTokens.surfaces.card} space-y-4`}
            aria-label="Request demo form"
            onSubmit={onSubmit}
          >
            <h2 className={marketingTokens.headingScale.h3}>Request a walkthrough</h2>
            <label className="block text-sm font-medium text-slate-800" htmlFor="work-email">Work email</label>
            <input
              id="work-email"
              name="email"
              type="email"
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              placeholder="you@fleetco.com"
            />
            <button type="submit" className={`${marketingTokens.buttonVariants.primary} w-full`} aria-label="Submit demo request">
              Request demo
            </button>
            {submitted ? <p className="text-sm text-emerald-700">Thanks, our team will follow up within 1 business day.</p> : null}
          </form>
        </div>
      </MarketingContainer>
    </header>
  );
}
