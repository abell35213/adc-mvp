import type { IntegrationOperationDiagnostics } from "@/lib/api";

type Props = {
  operation: IntegrationOperationDiagnostics | null;
  onClose: () => void;
};

type SuggestedAction = {
  label: string;
  href: string;
  description: string;
};

function getSuggestedActions(operation: IntegrationOperationDiagnostics): SuggestedAction[] {
  const reason = `${operation.error_message ?? ""} ${operation.error_operator_message ?? ""} ${operation.error_code ?? ""}`.toLowerCase();
  const suggestions: SuggestedAction[] = [];

  if (reason.includes("reauth") || reason.includes("token") || reason.includes("expired")) {
    suggestions.push({
      label: "Reconnect provider",
      href: "/settings/integrations",
      description: "Reauthenticate this connection to restore evidence ingestion.",
    });
  }

  if (operation.error_retryable || ["failed", "timed_out", "error"].includes(operation.status)) {
    suggestions.push({
      label: "Review retry policy",
      href: "/admin/ops",
      description: "Confirm retry backoff and queue handling for this provider.",
    });
  }

  if (operation.incident_id) {
    suggestions.push({
      label: "Open incident workspace",
      href: `/incidents/${operation.incident_id}`,
      description: "Verify captured evidence and assign the next remediation owner.",
    });
  }

  if (suggestions.length === 0) {
    suggestions.push({
      label: "Review integration health",
      href: "/settings/integrations",
      description: "Inspect provider and domain health for hidden blockers.",
    });
  }

  return suggestions;
}

export default function IntegrationOperationDrawer({ operation, onClose }: Props) {
  if (!operation) return null;

  const suggestedActions = getSuggestedActions(operation);

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="h-full w-full max-w-2xl overflow-y-auto bg-white p-5 shadow-xl dark:bg-gray-900"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-50">Operation diagnostics</h2>
          <button onClick={onClose} className="rounded border px-2 py-1 text-xs">Close</button>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-xs">
          <div><dt className="text-gray-500">Operation ID</dt><dd className="font-mono">{operation.operation_id}</dd></div>
          <div><dt className="text-gray-500">Status</dt><dd>{operation.status}</dd></div>
          <div><dt className="text-gray-500">Provider</dt><dd>{operation.provider}</dd></div>
          <div><dt className="text-gray-500">Domain</dt><dd>{operation.domain ?? "—"}</dd></div>
          <div><dt className="text-gray-500">Org</dt><dd className="font-mono">{operation.org_id ?? "—"}</dd></div>
          <div><dt className="text-gray-500">Correlation ID</dt><dd className="font-mono">{operation.correlation_id ?? "—"}</dd></div>
          <div><dt className="text-gray-500">Error code</dt><dd>{operation.error_code ?? "—"}</dd></div>
          <div><dt className="text-gray-500">Retryable</dt><dd>{operation.error_retryable == null ? "—" : operation.error_retryable ? "Yes" : "No"}</dd></div>
        </dl>

        <div className="mt-4 space-y-4 text-xs">
          <section>
            <h3 className="font-semibold">Suggested next action</h3>
            <div className="mt-2 space-y-2">
              {suggestedActions.map((action) => (
                <a key={`${action.label}-${action.href}`} href={action.href} className="block rounded border p-2 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
                  <p className="font-medium text-blue-700 dark:text-blue-300">{action.label}</p>
                  <p className="mt-1 text-gray-600 dark:text-gray-300">{action.description}</p>
                </a>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-semibold">Error details</h3>
            <p className="mt-1 rounded border bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-800">{operation.error_message ?? "No error message"}</p>
            {operation.error_operator_message && (
              <p className="mt-2 rounded border border-amber-300 bg-amber-50 p-2 text-amber-800 dark:bg-amber-950/40 dark:text-amber-100">{operation.error_operator_message}</p>
            )}
          </section>

          <section>
            <h3 className="font-semibold">Request payload</h3>
            <pre className="mt-1 overflow-x-auto rounded border bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-800">{JSON.stringify(operation.payload_json, null, 2)}</pre>
          </section>

          <section>
            <h3 className="font-semibold">Provider result</h3>
            <pre className="mt-1 overflow-x-auto rounded border bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-800">{JSON.stringify(operation.result_json, null, 2)}</pre>
          </section>
        </div>
      </aside>
    </div>
  );
}
