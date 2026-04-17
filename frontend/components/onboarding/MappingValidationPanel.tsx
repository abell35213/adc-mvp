import type { OnboardingStepStatus, OnboardingBlocker } from "@/lib/api";
import MappingIssuesTable from "@/components/onboarding/MappingIssuesTable";
import { formatStatus, getStatusClasses } from "@/components/onboarding/status";
import Link from "next/link";

type MappingValidationPanelProps = {
  status: OnboardingStepStatus;
  blockers: OnboardingBlocker[];
};

export default function MappingValidationPanel({ status, blockers }: MappingValidationPanelProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Mapping validation</h2>
          <p className="text-sm text-gray-600">Mark and review step status before launch.</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${getStatusClasses(status)}`}>{formatStatus(status)}</span>
      </header>

      <div className="mt-4 space-y-2">
        <p className="text-sm font-semibold text-gray-800">Blockers and remediation actions</p>
        <div className="flex gap-3 text-xs">
          <Link href="/dashboard?blockers=critical" className="font-semibold text-blue-700 hover:underline">View blockers</Link>
          <Link href="/settings/integrations" className="font-semibold text-blue-700 hover:underline">Open remediation actions</Link>
        </div>
      </div>

      <div className="mt-4">
        <MappingIssuesTable blockers={blockers} />
      </div>
    </section>
  );
}
