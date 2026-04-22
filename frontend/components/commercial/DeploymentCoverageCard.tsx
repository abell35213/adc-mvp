interface DeploymentCoverageCardProps {
  region: string;
  coveragePercent: number;
  gapCount: number;
}

export default function DeploymentCoverageCard({ region, coveragePercent, gapCount }: DeploymentCoverageCardProps) {
  return (
    <article className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <p className="text-sm font-medium text-gray-600 dark:text-gray-300">{region}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{coveragePercent}%</p>
      <p className="text-xs text-gray-500">Fleet QR + protocol deployment coverage</p>
      <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">Open coverage gaps: {gapCount}</p>
    </article>
  );
}
