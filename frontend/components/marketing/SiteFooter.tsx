import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";

const navLinks = [
  { label: "Product", href: "/product" },
  { label: "Solutions", href: "/solutions" },
  { label: "Pricing", href: "/pricing" },
  { label: "Resources", href: "/resources" },
  { label: "Company", href: "/company" },
  { label: "Contact", href: "/company/contact" },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50">
      {/* Final CTA band */}
      <div className="bg-sky-900 py-14 text-white">
        <MarketingContainer>
          <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:justify-between sm:text-left">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">
                Ready to operate smarter?
              </h2>
              <p className="mt-1 text-sky-200 text-sm">
                Reduce risk and improve visibility with one scalable platform.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center rounded-md bg-white px-5 py-3 text-sm font-semibold text-sky-900 shadow-sm transition hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                aria-label="Get pricing"
              >
                Get Pricing
              </Link>
              <Link
                href="/company/contact"
                className="inline-flex items-center justify-center rounded-md border border-sky-400 px-5 py-3 text-sm font-semibold text-white transition hover:bg-sky-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                aria-label="Book a demo"
              >
                Book Demo
              </Link>
            </div>
          </div>
        </MarketingContainer>
      </div>

      {/* Footer nav */}
      <MarketingContainer>
        <div className="flex flex-col items-center gap-6 py-10 sm:flex-row sm:justify-between">
          <span className="text-sm font-semibold uppercase tracking-[0.2em] text-sky-700">ADC</span>
          <nav aria-label="Footer navigation">
            <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-slate-600" role="list">
              {navLinks.map(({ label, href }) => (
                <li key={label}>
                  <Link
                    href={href}
                    className="hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <p className="text-xs text-slate-400">© {new Date().getFullYear()} ADC. All rights reserved.</p>
        </div>
      </MarketingContainer>
    </footer>
  );
}
