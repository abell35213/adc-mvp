import Link from "next/link";

export type OnboardingStepCardProps = {
  title: string;
  description: string;
  status: "completed" | "in_progress" | "not_started" | "blocked";
  href: string;
  ctaLabel: string;
};

const STATUS_STYLES: Record<OnboardingStepCardProps["status"], string> = {
  completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  in_progress: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  blocked: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  not_started: "bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-200",
};

const STATUS_LABELS: Record<OnboardingStepCardProps["status"], string> = {
  completed: "Completed",
  in_progress: "In progress",
  blocked: "Blocked",
  not_started: "Not started",
};

export default function OnboardingStepCard({
  title,
  description,
  status,
  href,
  ctaLabel,
}: OnboardingStepCardProps) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
        <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${STATUS_STYLES[status]}`}>
          {STATUS_LABELS[status]}
        </span>
      </div>
      <p className="mt-2 text-xs text-gray-600 dark:text-gray-300">{description}</p>
      <Link
        href={href}
        className="mt-3 inline-flex text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
      >
        {ctaLabel}
      </Link>
    </article>
  );
}
