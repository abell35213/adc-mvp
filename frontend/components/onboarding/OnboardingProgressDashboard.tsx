import { useMemo } from "react";
import Link from "next/link";
import BlockersPanel from "./BlockersPanel";
import LaunchReadinessHero from "./LaunchReadinessHero";
import type {
  IntegrationValidationResult,
  OrgLaunchReadiness,
  VehicleQrStats,
} from "@/lib/api";

type OnboardingProgressDashboardProps = {
  readiness: OrgLaunchReadiness | null;
  qrStats: VehicleQrStats | null;
  validationResults: IntegrationValidationResult[];
  loading: boolean;
};

type StepCard = {
  title: string;
  href: string;
  ctaLabel: string;
  completed: boolean;
  summary: string;
  missingCue: string;
};

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function toBadgeRecommendation(readiness: OrgLaunchReadiness | null): string {
  if (!readiness) return "Awaiting onboarding snapshot";
  if (readiness.status === "launch_ready") return "Ready to launch";
  if (readiness.blockers.some((item) => item.severity === "critical")) return "Resolve critical blockers";
  if (readiness.percent_complete >= 70) return "Run final validation";
  return "Complete setup steps";
}

export default function OnboardingProgressDashboard({
  readiness,
  qrStats,
  validationResults,
  loading,
}: OnboardingProgressDashboardProps) {
  const blockers = useMemo(
    () =>
      (readiness?.blockers ?? []).map((item) => ({
        ...item,
        severity: item.severity === "error" ? "critical" : item.severity,
      })),
    [readiness]
  );

  const importSummary = useMemo(() => {
    const jobs = readiness?.import_jobs ?? [];
    return {
      total: jobs.length,
      succeeded: jobs.filter((job) => job.status === "succeeded").length,
      failed: jobs.filter((job) => job.status === "failed").length,
    };
  }, [readiness]);

  const integrationHealth = useMemo(() => {
    if (validationResults.length === 0) return { passed: 0, total: 0 };
    return {
      passed: validationResults.filter(
        (item) =>
          item.credentialStatus === "completed" &&
          item.capabilityStatus === "completed" &&
          item.mappingStatus === "completed"
      ).length,
      total: validationResults.length,
    };
  }, [validationResults]);

  const stepCards: StepCard[] = [
    {
      title: "Protocol setup",
      href: "/admin/driver-protocol",
      ctaLabel: "Continue setup",
      completed: readiness?.steps.some((step) => step.status === "completed") ?? false,
      summary: "Configuration defaults and policy controls are defined.",
      missingCue: "Missing cue: assign an owner and finish protocol defaults.",
    },
    {
      title: "Validation checks",
      href: "/dashboard",
      ctaLabel: "Rerun validation",
      completed: readiness?.latest_export_validation?.status === "completed",
      summary: `Latest validation: ${formatDate(readiness?.latest_export_validation?.validated_at_utc)}`,
      missingCue: "Missing cue: run a fresh validation and clear failed checks.",
    },
    {
      title: "Data imports",
      href: "/settings/integrations",
      ctaLabel: "Import data",
      completed: importSummary.total > 0 && importSummary.failed === 0,
      summary: `${importSummary.succeeded}/${importSummary.total} jobs succeeded${importSummary.failed ? ` · ${importSummary.failed} failed` : ""}`,
      missingCue: "Missing cue: resolve failed imports and rerun connector sync.",
    },
    {
      title: "QR coverage",
      href: "/settings/integrations",
      ctaLabel: "Distribute QR codes",
      completed:
        (qrStats?.required_vehicle_count ?? 0) > 0 &&
        (qrStats?.distributed_count ?? 0) >= (qrStats?.required_vehicle_count ?? 0),
      summary: `${qrStats?.distributed_count ?? 0}/${qrStats?.required_vehicle_count ?? 0} vehicles covered.`,
      missingCue: "Missing cue: distribute codes to uncovered vehicles.",
    },
  ];

  return (
    <section className="space-y-4 rounded-xl border border-blue-100 bg-blue-50/40 p-4 dark:border-blue-900/40 dark:bg-blue-900/10">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Onboarding Progress Dashboard</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Track readiness, blockers, ownership, and the next best actions to reach go-live.
          </p>
        </div>
        {loading ? <span className="text-xs text-gray-500">Refreshing…</span> : null}
      </div>

      <LaunchReadinessHero
        percent={readiness?.percent_complete ?? 0}
        status={readiness?.status ?? "not_started"}
        recommendation={toBadgeRecommendation(readiness)}
        blockersCount={blockers.length}
        blockersHref="/dashboard?blockers=critical"
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Readiness steps</h3>
              <span className="text-xs text-gray-500">Completion + missing item cues</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {stepCards.map((step) => (
                <article key={step.title} className="rounded-md border border-gray-200 p-3 dark:border-gray-700">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{step.title}</h4>
                    <span
                      className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                        step.completed
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                          : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                      }`}
                    >
                      {step.completed ? "Completed" : "Needs action"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-gray-600 dark:text-gray-300">{step.summary}</p>
                  {!step.completed ? (
                    <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">{step.missingCue}</p>
                  ) : null}
                  <Link href={step.href} className="mt-3 inline-flex text-xs font-medium text-blue-600 hover:underline">
                    {step.ctaLabel}
                  </Link>
                </article>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-4">
          <BlockersPanel blockers={blockers} reviewHref="/dashboard?blockers=critical" />

          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Validation + imports</h3>
            <ul className="mt-3 space-y-2 text-xs text-gray-700 dark:text-gray-200">
              <li className="rounded-md border border-gray-200 bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-900">
                Integration validations passing: <span className="font-semibold">{integrationHealth.passed}/{integrationHealth.total}</span>
              </li>
              <li className="rounded-md border border-gray-200 bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-900">
                Import jobs: <span className="font-semibold">{importSummary.succeeded}/{importSummary.total}</span>
              </li>
              <li className="rounded-md border border-gray-200 bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-900">
                Latest checks recorded: <span className="font-semibold">{validationResults.length}</span>
              </li>
            </ul>
          </section>

          <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Help + next actions</h3>
            <div className="mt-3 flex flex-col gap-2 text-xs font-medium text-blue-700 dark:text-blue-300">
              <Link href="/settings/integrations" className="hover:underline">Invite users</Link>
              <Link href="/incidents" className="hover:underline">Run a test incident flow</Link>
              <Link href="/dashboard" className="hover:underline">Review export readiness</Link>
            </div>
          </section>
        </aside>
      </div>
    </section>
  );
}
