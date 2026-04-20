interface PlanBadgeProps {
  plan: "Starter" | "Growth" | "Enterprise";
}

const PLAN_STYLES: Record<PlanBadgeProps["plan"], string> = {
  Starter: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200",
  Growth: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200",
  Enterprise: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-200",
};

export default function PlanBadge({ plan }: PlanBadgeProps) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${PLAN_STYLES[plan]}`}>
      {plan}
    </span>
  );
}
