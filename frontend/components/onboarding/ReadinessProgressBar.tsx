type ReadinessProgressBarProps = {
  percent: number;
  label: string;
};

export default function ReadinessProgressBar({ percent, label }: ReadinessProgressBarProps) {
  const boundedPercent = Math.max(0, Math.min(100, percent));

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
