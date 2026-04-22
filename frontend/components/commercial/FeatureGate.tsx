import type { ReactNode } from "react";
import PlanBadge from "./PlanBadge";

interface FeatureGateProps {
  available: boolean;
  mode?: "hide" | "lock";
  reason?: string;
  requiredPlan?: "Starter" | "Growth" | "Enterprise";
  children: ReactNode;
}

export default function FeatureGate({
  available,
  mode = "lock",
  reason = "Not available for your current plan.",
  requiredPlan,
  children,
}: FeatureGateProps) {
  if (available) return <>{children}</>;
  if (mode === "hide") return null;

  return (
    <div className="space-y-2 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/50">
      <div className="flex flex-wrap items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
          Locked
        </span>
        {requiredPlan ? <PlanBadge plan={requiredPlan} /> : null}
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-300">{reason}</p>
      <div
        className="pointer-events-none select-none rounded-md opacity-60"
        aria-disabled="true"
        title={reason}
      >
        {children}
      </div>
    </div>
  );
}
