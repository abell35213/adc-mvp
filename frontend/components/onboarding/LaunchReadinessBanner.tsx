import Link from "next/link";
import type { OnboardingReadinessStatus } from "@/lib/api";

type LaunchReadinessBannerProps = {
  status: OnboardingReadinessStatus;
  recommendation: string;
};

const STATUS_LABELS: Record<OnboardingReadinessStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  blocked: "Blocked",
  pilot_ready: "Pilot ready",
  launch_ready: "Launch ready",
};

const STATUS_STYLES: Record<OnboardingReadinessStatus, string> = {
  not_started: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
  in_progress: "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200",
  blocked: "border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-200",
  pilot_ready: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200",
  launch_ready: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200",
};

export default function LaunchReadinessBanner({ status, recommendation }: LaunchReadinessBannerProps) {
  return (
    <section className={`rounded-lg border p-4 ${STATUS_STYLES[status]}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide">Overall status</p>
          <h3 className="text-lg font-semibold">{STATUS_LABELS[status]}</h3>
        </div>
        <span className="rounded-full border border-current px-3 py-1 text-xs font-semibold">
          Recommendation: {recommendation}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs font-medium">
        <Link href="/admin/driver-protocol" className="underline underline-offset-2">Continue setup</Link>
        <Link href="/dashboard" className="underline underline-offset-2">Rerun validation</Link>
        <Link href="/settings/integrations" className="underline underline-offset-2">Import data</Link>
        <Link href="/settings/integrations" className="underline underline-offset-2">Invite users</Link>
        <Link href="/incidents" className="underline underline-offset-2">Open test incident flow</Link>
      </div>
    </section>
  );
}
