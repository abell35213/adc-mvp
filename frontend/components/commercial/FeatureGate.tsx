import type { ReactNode } from "react";
import { statusBadgeClass } from "@/lib/design/tokens";
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
    <div className="space-y-2 rounded-lg border border-dashed border-border-strong bg-surface-muted p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
        <span className={`${statusBadgeClass("warning")} font-semibold`}>
          Locked
        </span>
        {requiredPlan ? <PlanBadge plan={requiredPlan} /> : null}
      </div>
      <p className="text-sm text-text-secondary">{reason}</p>
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
