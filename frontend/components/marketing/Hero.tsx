"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { Logo } from "@/components/marketing/Logo";
import { marketingTokens } from "@/components/marketing/tokens";
import { trackCtaClick } from "@/lib/tracking";

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
        <nav className="flex items-center justify-between gap-4 py-5" aria-label="Primary">
          <Link
            href="/"
            aria-label="ADC home"
            className="inline-flex items-center rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3] focus-visible:ring-offset-2 focus-visible:ring-offset-[#EBF2FA]"
          >
            <Logo variant="mark" height={72} priority />
          </Link>

          <div className="flex items-center gap-2 sm:gap-4">
            <Link href="/login" className={marketingTokens.buttonVariants.ghost}>
              Login
            </Link>
            <span
              aria-hidden="true"
              className="h-6 w-px bg-slate-300"
            />
            <Link href="/pricing" className={marketingTokens.buttonVariants.primary}>
              Check our Prices
            </Link>
            <Link href="/company/contact" className={marketingTokens.buttonVariants.primary}>
              Book a Demo
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
