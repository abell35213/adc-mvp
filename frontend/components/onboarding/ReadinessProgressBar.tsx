type ReadinessProgressBarProps = {
  percent: number;
  label: string;
  variant?: "bar" | "ring";
  size?: number;
};

export default function ReadinessProgressBar({
  percent,
  label,
  variant = "bar",
  size = 112,
}: ReadinessProgressBarProps) {
  const boundedPercent = Math.max(0, Math.min(100, Math.round(percent)));

  if (variant === "ring") {
    const strokeWidth = 10;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const dashOffset = circumference * (1 - boundedPercent / 100);

    return (
      <div className="inline-flex flex-col items-center gap-2" role="img" aria-label={`${label}: ${boundedPercent}%`}>
        <div className="relative" style={{ width: size, height: size }}>
          <svg className="-rotate-90" width={size} height={size}>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-slate-200 dark:text-slate-700"
              fill="none"
            />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="text-blue-600 dark:text-blue-400"
              fill="none"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-semibold text-gray-900 dark:text-gray-100">{boundedPercent}%</span>
          </div>
        </div>
        <p className="text-xs font-medium text-gray-600 dark:text-gray-300">{label}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-medium text-gray-600 dark:text-gray-300">{label}</p>
        <p className="text-xs font-semibold text-gray-900 dark:text-gray-100">{boundedPercent}%</p>
      </div>
      <div className="h-2.5 rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-2.5 rounded-full bg-blue-600 transition-all"
          style={{ width: `${boundedPercent}%` }}
          aria-label={`${boundedPercent}% complete`}
        />
      </div>
    </div>
  );
}
