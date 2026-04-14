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
    <div className="rounded-md border bg-gray-50 p-3 dark:bg-gray-900/40">
      <p className="text-xs text-gray-500">Case owner</p>
      <p className="mt-1 font-mono text-xs text-gray-800 dark:text-gray-200">
        {ownerUserId ? `${ownerUserId.slice(0, 8)}…` : "Unassigned"}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          onClick={() => run(onAssignMe)}
          disabled={busy}
          className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          Assign me
        </button>
        <button
          onClick={() => run(onClearOwner)}
          disabled={busy || !ownerUserId}
          className="rounded border px-2 py-1 text-xs hover:bg-gray-100 disabled:opacity-60 dark:border-gray-600 dark:hover:bg-gray-700"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
