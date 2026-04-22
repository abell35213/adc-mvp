import type { OnboardingBlocker } from "@/lib/api";
import Link from "next/link";

type MappingIssuesTableProps = {
  blockers: OnboardingBlocker[];
};

const REMEDIATION_LINK = "/onboarding/integration-setup";

export default function MappingIssuesTable({ blockers }: MappingIssuesTableProps) {
  if (blockers.length === 0) {
    return <p className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">No mapping blockers found.</p>;
  }

  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-600">
          <tr>
            <th className="px-3 py-2">Issue</th>
            <th className="px-3 py-2">Severity</th>
            <th className="px-3 py-2">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {blockers.map((blocker) => (
            <tr key={blocker.code}>
              <td className="px-3 py-3">
                <p className="font-semibold text-gray-900">{blocker.title}</p>
                <p className="text-xs text-gray-600">{blocker.detail}</p>
              </td>
              <td className="px-3 py-3 text-xs font-semibold uppercase text-amber-700">{blocker.severity}</td>
              <td className="px-3 py-3">
                <Link href={REMEDIATION_LINK} className="text-xs font-semibold text-blue-700 hover:underline">
                  Open remediation actions
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
