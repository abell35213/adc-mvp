import type { OnboardingBlocker, OnboardingStepStatus } from "@/lib/api";
import { formatStatus, getStatusClasses } from "@/components/onboarding/status";
import Link from "next/link";

type SampleIncidentRunPanelProps = {
  status: OnboardingStepStatus;
  blockers: OnboardingBlocker[];
};

export default function SampleIncidentRunPanel({ status, blockers }: SampleIncidentRunPanelProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-900">Sample incident validation</h2>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${getStatusClasses(status)}`}>{formatStatus(status)}</span>
      </div>
      <p className="mt-1 text-sm text-gray-600">Run a dry-run incident and resolve blockers before launch sign-off.</p>

      <div className="mt-3 flex gap-3 text-xs">
        <Link href="/dashboard?blockers=critical" className="font-semibold text-blue-700 hover:underline">View blockers</Link>
        <Link href="/incidents" className="font-semibold text-blue-700 hover:underline">Open remediation actions</Link>
      </div>

      <div className="mt-4">
        {blockers.length === 0 ? (
          <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">No sample incident blockers reported.</p>
        ) : (
          <ul className="space-y-2">
            {blockers.map((blocker) => (
              <li key={blocker.code} className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
                <p className="font-semibold text-amber-900">{blocker.title}</p>
                <p className="text-amber-800">{blocker.detail}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
