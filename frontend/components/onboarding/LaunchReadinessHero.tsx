import LaunchReadinessBanner from "./LaunchReadinessBanner";
import ReadinessProgressBar from "./ReadinessProgressBar";

type LaunchReadinessHeroProps = {
  percent: number;
  status: "not_started" | "in_progress" | "blocked" | "pilot_ready" | "launch_ready";
  recommendation: string;
  blockersCount: number;
  blockersHref: string;
};

export default function LaunchReadinessHero({
  percent,
  status,
  recommendation,
  blockersCount,
  blockersHref,
}: LaunchReadinessHeroProps) {
  return (
    <section className="rounded-xl border border-blue-100 bg-white p-4 shadow-sm dark:border-blue-900/50 dark:bg-gray-800">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <ReadinessProgressBar label="Launch readiness" percent={percent} variant="ring" />
        <div className="min-w-0 flex-1">
          <LaunchReadinessBanner
            status={status}
            recommendation={recommendation}
            blockersCount={blockersCount}
            blockersHref={blockersHref}
          />
        </div>
      </div>
    </section>
  );
}
