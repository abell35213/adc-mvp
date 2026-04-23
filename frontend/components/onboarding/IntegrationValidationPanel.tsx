import type { IntegrationValidationResult, OnboardingStepStatus } from "@/lib/api";
import { formatStatus, getStatusClasses } from "@/components/onboarding/status";
import Link from "next/link";

type IntegrationValidationPanelProps = {
  status: OnboardingStepStatus;
  results: IntegrationValidationResult[];
};

export default function IntegrationValidationPanel({ status, results }: IntegrationValidationPanelProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-900">Integration setup validation</h2>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${getStatusClasses(status)}`}>{formatStatus(status)}</span>
      </div>
      <p className="mt-1 text-sm text-gray-600">Track validation status and jump directly to blocker and remediation workflows.</p>

      <div className="mt-3 flex gap-3 text-xs">
        <Link href="/dashboard?blockers=critical" className="font-semibold text-blue-700 hover:underline">View blockers</Link>
        <Link href="/settings/integrations" className="font-semibold text-blue-700 hover:underline">Open remediation actions</Link>
      </div>

      <ul className="mt-4 space-y-2">
        {results.length === 0 ? (
          <li className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">No integration checks yet.</li>
        ) : (
          results.map((result) => (
            <li key={`${result.integration_id}-${result.timestamp}`} className="rounded border border-gray-200 px-3 py-2 text-sm">
              <p className="font-semibold text-gray-900">{result.integration_id}</p>
              <p className="text-xs text-gray-600">
                Credential: {formatStatus(result.credentialStatus)} · Capability: {formatStatus(result.capabilityStatus)} · Mapping: {formatStatus(result.mappingStatus)}
              </p>
              {result.messages.length > 0 ? <p className="mt-1 text-xs text-amber-700">{result.messages.join(" • ")}</p> : null}
            </li>
          ))
        )}
      </ul>
    </section>
  );
}
