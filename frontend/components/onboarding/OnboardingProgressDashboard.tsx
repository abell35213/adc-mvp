import { useMemo } from "react";
import Link from "next/link";
import BlockersPanel from "./BlockersPanel";
import LaunchReadinessBanner from "./LaunchReadinessBanner";
import OnboardingStepCard from "./OnboardingStepCard";
import ReadinessProgressBar from "./ReadinessProgressBar";
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

function getStepStatus(score: number): "completed" | "in_progress" | "not_started" {
  if (score >= 1) return "completed";
  if (score > 0) return "in_progress";
  return "not_started";
}

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
    () => (readiness?.blockers ?? []).map((item) => ({ ...item, severity: item.severity === "error" ? "critical" : item.severity })),
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

  const latestValidationTime = readiness?.latest_export_validation?.validated_at_utc;

  const setupScore = readiness
    ? readiness.steps.length === 0
      ? 0
      : readiness.steps.filter((step) => step.status === "completed").length / readiness.steps.length
    : 0;

  return (
    <section className="space-y-4 rounded-xl border border-blue-100 bg-blue-50/40 p-4 dark:border-blue-900/40 dark:bg-blue-900/10">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Onboarding Progress Dashboard</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300">Track readiness, blockers, validation signals, and launch recommendations.</p>
        </div>
        {loading ? <span className="text-xs text-gray-500">Refreshing…</span> : null}
      </div>

      <LaunchReadinessBanner
        status={readiness?.status ?? "not_started"}
        recommendation={toBadgeRecommendation(readiness)}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 lg:col-span-2">
          <ReadinessProgressBar
            label="Overall launch readiness"
            percent={readiness?.percent_complete ?? 0}
          />
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <OnboardingStepCard
              title="Setup"
              description="Finish protocol configuration and defaults"
              status={getStepStatus(setupScore)}
              href="/admin/driver-protocol"
              ctaLabel="Continue setup"
            />
            <OnboardingStepCard
              title="Validation"
              description={`Latest export validation: ${formatDate(latestValidationTime)}`}
              status={readiness?.latest_export_validation?.status ?? "not_started"}
              href="/dashboard"
              ctaLabel="Rerun validation"
            />
            <OnboardingStepCard
              title="Imports"
              description={`${importSummary.succeeded}/${importSummary.total} jobs succeeded${importSummary.failed ? ` · ${importSummary.failed} failed` : ""}`}
              status={importSummary.total === 0 ? "not_started" : importSummary.failed > 0 ? "in_progress" : "completed"}
              href="/settings/integrations"
              ctaLabel="Import data"
            />
          </div>

          <div className="mt-4 grid gap-3 text-xs text-gray-700 dark:text-gray-200 sm:grid-cols-3">
            <div className="rounded-md border bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900">
              <p className="text-[11px] uppercase text-gray-500">Integration health</p>
              <p className="mt-1 text-base font-semibold">{integrationHealth.passed}/{integrationHealth.total}</p>
              <p className="text-[11px] text-gray-500">validations passing</p>
            </div>
            <div className="rounded-md border bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900">
              <p className="text-[11px] uppercase text-gray-500">QR coverage</p>
              <p className="mt-1 text-base font-semibold">
                {qrStats?.distributed_count ?? 0}/{qrStats?.required_vehicle_count ?? 0}
              </p>
              <p className="text-[11px] text-gray-500">distributed vehicles</p>
            </div>
            <div className="rounded-md border bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900">
              <p className="text-[11px] uppercase text-gray-500">Recent validations</p>
              <p className="mt-1 text-base font-semibold">{validationResults.length}</p>
              <p className="text-[11px] text-gray-500">latest integration checks</p>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3 text-xs font-medium text-blue-700 dark:text-blue-300">
            <Link href="/settings/integrations" className="hover:underline">Invite users</Link>
            <Link href="/incidents" className="hover:underline">Open test incident flow</Link>
          </div>
        </div>

        <BlockersPanel blockers={blockers} reviewHref="/dashboard?blockers=critical" />
      </div>
    </section>
  );
}
