"use client";

import { useState } from "react";

interface CaseOwnerControlProps {
  ownerUserId?: string | null;
  onAssignMe: () => Promise<void>;
  onClearOwner: () => Promise<void>;
}

export default function CaseOwnerControl({ ownerUserId, onAssignMe, onClearOwner }: CaseOwnerControlProps) {
  const [busy, setBusy] = useState(false);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Owner</p>
      <p className="mt-1 text-sm font-medium text-gray-900">{ownerUserId ? `${ownerUserId.slice(0, 8)}…` : "Unassigned"}</p>
      <div className="mt-3 flex gap-2">
        <button onClick={() => run(onAssignMe)} disabled={busy} className="rounded bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60">Assign me</button>
        <button onClick={() => run(onClearOwner)} disabled={busy || !ownerUserId} className="rounded border border-gray-300 px-2.5 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-60">Clear</button>
      </div>
    </section>
  );
}
