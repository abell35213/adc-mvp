interface PlanBadgeProps {
  plan: "Starter" | "Growth" | "Enterprise";
}

const PLAN_STYLES: Record<PlanBadgeProps["plan"], string> = {
  Starter: "bg-surface text-text-secondary",
  Growth: "bg-accent-soft text-accent",
  Enterprise: "bg-status-info-soft text-status-info",
};

export default function PlanBadge({ plan }: PlanBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${PLAN_STYLES[plan]}`}>
      {plan}
    </span>
  );
}
