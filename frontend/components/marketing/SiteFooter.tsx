import Link from "next/link";
import { MarketingContainer } from "@/components/marketing/LayoutPrimitives";
import { Logo } from "@/components/marketing/Logo";

const footerSections = [
  {
    title: "Solutions",
    links: [
      { label: "Fleet Safety", href: "/solutions/fleet-safety" },
      { label: "Claims Defense", href: "/solutions/claims-defense" },
      { label: "Compliance", href: "/solutions/compliance" },
    ],
  },
  {
    title: "Platform",
    links: [
      { label: "Platform Overview", href: "/platform" },
      { label: "Evidence Vault", href: "/platform/evidence-vault" },
      { label: "Driver Protocol", href: "/platform/driver-protocol" },
      { label: "Exports", href: "/platform/exports" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Resource Hub", href: "/resources" },
      { label: "Sample Documents", href: "/resources/sample-documents" },
      { label: "Case Studies", href: "/resources/case-studies" },
      { label: "Blog", href: "/resources/blog" },
      { label: "Docs", href: "/resources/docs" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Company Overview", href: "/company" },
      { label: "About", href: "/company/about" },
      { label: "Contact", href: "/company/contact" },
      { label: "Careers", href: "/company/careers" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-100 bg-white">
      <div className="bg-[#062040] py-14 text-white">
        <MarketingContainer>
          <div className="flex flex-col items-center gap-6 text-center sm:flex-row sm:justify-between sm:text-left">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Ready to operate smarter?</h2>
              <p className="mt-1 text-sm text-slate-300">
                Reduce risk and improve fleet visibility with one scalable platform.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center rounded-full bg-[#1B6EF3] px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[#1558c9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              >
                Check Our Prices
              </Link>
              <Link
                href="/company/contact"
                className="inline-flex items-center justify-center rounded-full border border-slate-500 px-6 py-3 text-sm font-bold text-white transition hover:border-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
              >
                Book a Demo
              </Link>
            </div>
          </div>
        </MarketingContainer>
      </div>

      <MarketingContainer>
        <div className="py-10">
          <div className="grid gap-8 md:grid-cols-6">
            <div>
              <Link
                href="/"
                aria-label="ADC home"
                className="inline-flex items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
              >
                <Logo variant="mark" height={32} />
                <span className="text-lg font-bold text-[#062040]">ADC</span>
              </Link>
            </div>
            {footerSections.map((section) => (
              <nav key={section.title} aria-label={section.title}>
                <h3 className="mb-3 text-sm font-semibold text-[#062040]">{section.title}</h3>
                <ul className="space-y-2 text-sm text-slate-500" role="list">
                  {section.links.map(({ label, href }) => (
                    <li key={label}>
                      <Link
                        href={href}
                        className="transition hover:text-[#062040] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1B6EF3]"
                      >
                        {label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
          <p className="mt-8 text-xs text-slate-400">© {new Date().getFullYear()} ADC. All rights reserved.</p>
        </div>
      </MarketingContainer>
    </footer>
  );
}
