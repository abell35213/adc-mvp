import Link from "next/link";

interface CaseHeroHeaderProps {
  incidentId: string;
  createdAtLabel: string;
  whatHappened: string;
  nextAction: string;
  captured: number;
  total: number;
  pending: number;
  unavailable: number;
}

export default function CaseHeroHeader({
  incidentId,
  createdAtLabel,
  whatHappened,
  nextAction,
  captured,
  total,
  pending,
  unavailable,
}: CaseHeroHeaderProps) {
  return (
    <header className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/incidents" className="text-sm text-blue-600 hover:underline">
            ← Back to incidents
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-gray-900">Case {incidentId.slice(0, 8)}…</h1>
          <p className="mt-1 text-xs text-gray-500">Opened {createdAtLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-green-100 px-2 py-1 font-medium text-green-800">Captured {captured}/{total}</span>
          {pending > 0 ? <span className="rounded-full bg-yellow-100 px-2 py-1 font-medium text-yellow-800">Pending {pending}</span> : null}
          {unavailable > 0 ? <span className="rounded-full bg-red-100 px-2 py-1 font-medium text-red-800">Unavailable {unavailable}</span> : null}
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">What happened</p>
          <p className="mt-1 text-sm text-gray-800">{whatHappened}</p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Next action</p>
          <p className="mt-1 text-sm font-medium text-blue-900">{nextAction}</p>
        </div>
      </div>
    </header>
  );
}
