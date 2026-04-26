import Link from "next/link";
import type { ReactNode } from "react";

type Breadcrumb = {
  label: string;
  href?: string;
};

type SidebarHelpLink = {
  label: string;
  href: string;
};

type FooterAction = {
  label: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
};

type OnboardingStepLayoutProps = {
  title: string;
  breadcrumbs: Breadcrumb[];
  progressRow: ReactNode;
  children: ReactNode;
  whyThisMatters: ReactNode;
  requirements: string[];
  blockingIssues: ReactNode;
  helpLinks: SidebarHelpLink[];
  onSaveExitHref?: string;
  backAction?: FooterAction;
  saveDraftAction?: FooterAction;
  continueAction?: FooterAction;
};

function HeaderAction({ action, variant }: { action?: FooterAction; variant: "primary" | "secondary" }) {
  if (!action) return null;

  const baseClassName =
    variant === "primary"
      ? "rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white"
      : "rounded border border-gray-300 px-3 py-2 text-sm text-gray-700";
  const disabledClassName = action.disabled ? " cursor-not-allowed opacity-50 pointer-events-none" : "";
  const className = `${baseClassName}${disabledClassName}`;

  if (action.href) {
    if (action.disabled) {
      return (
        <span aria-disabled="true" className={className}>
          {action.label}
        </span>
      );
    }

    return (
      <Link className={className} href={action.href}>
        {action.label}
      </Link>
    );
  }

  return (
    <button className={className} disabled={action.disabled} onClick={action.onClick} type="button">
      {action.label}
    </button>
  );
}

export default function OnboardingStepLayout({
  title,
  breadcrumbs,
  progressRow,
  children,
  whyThisMatters,
  requirements,
  blockingIssues,
  helpLinks,
  onSaveExitHref = "/onboarding",
  backAction,
  saveDraftAction,
  continueAction,
}: OnboardingStepLayoutProps) {
  return (
    <div className="space-y-4">
      <header className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <nav className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
              {breadcrumbs.map((crumb, index) => (
                <span className="flex items-center gap-2" key={`${crumb.label}-${index}`}>
                  {crumb.href ? <Link className="hover:text-blue-700" href={crumb.href}>{crumb.label}</Link> : <span>{crumb.label}</span>}
                  {index < breadcrumbs.length - 1 ? <span aria-hidden="true">/</span> : null}
                </span>
              ))}
            </nav>
            <h2 className="mt-2 text-2xl font-semibold text-gray-900">{title}</h2>
          </div>
          <Link className="rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700" href={onSaveExitHref}>
            Save &amp; Exit
          </Link>
        </div>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-4">{progressRow}</section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="rounded-lg border border-gray-200 bg-white p-4">{children}</section>

        <aside className="space-y-3">
          <section className="rounded-lg border border-blue-100 bg-blue-50 p-3">
            <h3 className="text-sm font-semibold text-blue-900">Why this matters</h3>
            <div className="mt-2 text-sm text-blue-800">{whyThisMatters}</div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-3">
            <h3 className="text-sm font-semibold text-gray-900">Requirements</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700">
              {requirements.map((requirement) => (
                <li key={requirement}>{requirement}</li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg border border-amber-200 bg-amber-50 p-3">
            <h3 className="text-sm font-semibold text-amber-900">Blocking Issues</h3>
            <div className="mt-2 text-sm text-amber-900">{blockingIssues}</div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-3">
            <h3 className="text-sm font-semibold text-gray-900">Help Links</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {helpLinks.map((link) => (
                <li key={link.href}>
                  <Link className="font-medium text-blue-700 hover:underline" href={link.href}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <footer className="sticky bottom-0 rounded-lg border border-gray-200 bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <HeaderAction action={backAction} variant="secondary" />
          <div className="flex gap-2">
            <HeaderAction action={saveDraftAction} variant="secondary" />
            <HeaderAction action={continueAction} variant="primary" />
          </div>
        </div>
      </footer>
    </div>
  );
}
