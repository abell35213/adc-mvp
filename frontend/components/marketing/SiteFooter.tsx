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
    <footer className="bg-white border-t border-slate-100">
      {/* Final CTA band */}
      <div className="bg-[#062040] py-14 text-white">
        <MarketingContainer>
          <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:justify-between sm:text-left">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">
                Ready to operate smarter?
              </h2>
              <p className="mt-1 text-slate-300 text-sm">
                Reduce risk and improve fleet visibility with one scalable platform.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center rounded-full bg-[#1B6EF3] px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                aria-label="Check our prices"
              >
                Check Our Prices
              </Link>
              <Link
                href="/company/contact"
                className="inline-flex items-center justify-center rounded-full border border-slate-500 px-6 py-3 text-sm font-bold text-white transition hover:border-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
                aria-label="Try the demo"
              >
                Try the Demo
              </Link>
            </div>
          </div>
        </MarketingContainer>
      </div>

      {/* Footer nav */}
      <MarketingContainer>
        <div className="flex flex-col items-center gap-6 py-10 sm:flex-row sm:justify-between">
          <span className="text-lg font-bold text-[#062040]">ADC</span>
          <nav aria-label="Footer navigation">
            <ul className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-slate-500" role="list">
              {navLinks.map(({ label, href }) => (
                <li key={label}>
                  <Link
                    href={href}
                    className="hover:text-[#062040] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
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
