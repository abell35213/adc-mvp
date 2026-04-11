"use client";

import { useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import {
  getIntegrationConnections,
  getIntegrationOperations,
  type IntegrationConnectionHealth,
  type IntegrationOperationDiagnostics,
} from "@/lib/api";
import IntegrationConnectionCard from "./IntegrationConnectionCard";
import IntegrationHealthTable from "./IntegrationHealthTable";
import IntegrationOperationTable from "./IntegrationOperationTable";
import IntegrationOperationDrawer from "./IntegrationOperationDrawer";

export type IntegrationHealthSummary = {
  provider: string;
  domain: string | null;
  successRate: number;
  timeoutRate: number;
  stuckOps: number;
  retryCount: number;
  topNormalizedCodes: string[];
};

const TIME_RANGE_HOURS: Record<string, number> = {
  "24h": 24,
  "72h": 72,
  "7d": 168,
  "30d": 720,
};

function normalizeErrorCode(operation: IntegrationOperationDiagnostics) {
  if (operation.error_category) return operation.error_category.toUpperCase();
  if (operation.error_code) return operation.error_code.toUpperCase();
  if ((operation.error_message ?? "").toLowerCase().includes("timeout")) return "TIMEOUT";
  return "NONE";
}

function isStuck(operation: IntegrationOperationDiagnostics, now: number) {
  if (!["queued", "running", "processing_at_provider"].includes(operation.status)) return false;
  const requested = operation.requested_at_utc ? new Date(operation.requested_at_utc).getTime() : 0;
  return requested > 0 && now - requested > 30 * 60 * 1000;
}

export default function IntegrationSettingsPage() {
  const [connections, setConnections] = useState<IntegrationConnectionHealth[]>([]);
  const [operations, setOperations] = useState<IntegrationOperationDiagnostics[]>([]);
  const [selected, setSelected] = useState<IntegrationOperationDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [orgFilter, setOrgFilter] = useState("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [domainFilter, setDomainFilter] = useState("all");
  const [timeRange, setTimeRange] = useState<keyof typeof TIME_RANGE_HOURS>("7d");

  useEffect(() => {
    Promise.all([getIntegrationConnections(), getIntegrationOperations({ limit: 500 })])
      .then(([connectionRows, operationRows]) => {
        setConnections(connectionRows);
        setOperations(operationRows);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load integration diagnostics");
      })
      .finally(() => setLoading(false));
  }, []);

  const orgOptions = useMemo(
    () => Array.from(new Set(operations.map((op) => op.org_id).filter(Boolean) as string[])).sort(),
    [operations]
  );
  const providerOptions = useMemo(
    () => Array.from(new Set(operations.map((op) => op.provider))).sort(),
    [operations]
  );
  const domainOptions = useMemo(
    () => Array.from(new Set(operations.map((op) => op.domain).filter(Boolean) as string[])).sort(),
    [operations]
  );

  const filteredOperations = useMemo(() => {
    const referenceTime = operations.reduce((latest, op) => {
      const requested = op.requested_at_utc ? new Date(op.requested_at_utc).getTime() : 0;
      return requested > latest ? requested : latest;
    }, 0);
    const since = referenceTime - TIME_RANGE_HOURS[timeRange] * 60 * 60 * 1000;
    return operations.filter((op) => {
      const requested = op.requested_at_utc ? new Date(op.requested_at_utc).getTime() : 0;
      if (requested && requested < since) return false;
      if (orgFilter !== "all" && op.org_id !== orgFilter) return false;
      if (providerFilter !== "all" && op.provider !== providerFilter) return false;
      if (domainFilter !== "all" && (op.domain ?? "") !== domainFilter) return false;
      return true;
    });
  }, [operations, orgFilter, providerFilter, domainFilter, timeRange]);

  const healthRows = useMemo<IntegrationHealthSummary[]>(() => {
    const referenceNow = filteredOperations.reduce((latest, item) => {
      const requested = item.requested_at_utc ? new Date(item.requested_at_utc).getTime() : 0;
      return requested > latest ? requested : latest;
    }, 0);
    const grouped = new Map<string, IntegrationOperationDiagnostics[]>();
    for (const operation of filteredOperations) {
      const key = `${operation.provider}__${operation.domain ?? ""}`;
      grouped.set(key, [...(grouped.get(key) ?? []), operation]);
    }

    return Array.from(grouped.entries()).map(([key, rows]) => {
      const [provider, domainRaw] = key.split("__");
      const total = rows.length || 1;
      const success = rows.filter((row) => ["succeeded", "available", "downloaded"].includes(row.status)).length;
      const timeout = rows.filter((row) => normalizeErrorCode(row) === "TIMEOUT").length;
      const stuckOps = rows.filter((row) => isStuck(row, referenceNow)).length;
      const retryCount = rows.reduce((sum, row) => {
        const retryFromResult = row.result_json["retry_count"];
        const retryFromPayload = row.payload_json["retry_count"];
        const next = Number(
          (typeof retryFromResult === "number" ? retryFromResult : undefined) ??
          (typeof retryFromPayload === "number" ? retryFromPayload : undefined) ??
          0
        );
        return sum + (Number.isNaN(next) ? 0 : next);
      }, 0);

      const errorCounts = new Map<string, number>();
      rows.forEach((row) => {
        const code = normalizeErrorCode(row);
        if (code === "NONE") return;
        errorCounts.set(code, (errorCounts.get(code) ?? 0) + 1);
      });

      const topNormalizedCodes = Array.from(errorCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([code, count]) => `${code} (${count})`);

      return {
        provider,
        domain: domainRaw || null,
        successRate: success / total,
        timeoutRate: timeout / total,
        stuckOps,
        retryCount,
        topNormalizedCodes,
      };
    });
  }, [filteredOperations]);

  const visibleConnections = useMemo(
    () =>
      connections.filter((connection) => {
        if (providerFilter !== "all" && connection.provider !== providerFilter) return false;
        if (domainFilter !== "all" && (connection.domain ?? "") !== domainFilter) return false;
        return true;
      }),
    [connections, providerFilter, domainFilter]
  );

  return (
    <MainLayout title="Integration Settings & Diagnostics">
      <div className="space-y-5">
        <section className="rounded-lg border bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-50">Filters</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <label className="text-xs">Org
              <select value={orgFilter} onChange={(e) => setOrgFilter(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                <option value="all">All orgs</option>
                {orgOptions.map((org) => <option key={org} value={org}>{org}</option>)}
              </select>
            </label>
            <label className="text-xs">Provider
              <select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                <option value="all">All providers</option>
                {providerOptions.map((provider) => <option key={provider} value={provider}>{provider}</option>)}
              </select>
            </label>
            <label className="text-xs">Domain
              <select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                <option value="all">All domains</option>
                {domainOptions.map((domain) => <option key={domain} value={domain}>{domain}</option>)}
              </select>
            </label>
            <label className="text-xs">Time range
              <select value={timeRange} onChange={(e) => setTimeRange(e.target.value as keyof typeof TIME_RANGE_HOURS)} className="mt-1 w-full rounded border px-2 py-1 dark:border-gray-600 dark:bg-gray-900">
                {Object.keys(TIME_RANGE_HOURS).map((range) => <option key={range} value={range}>{range}</option>)}
              </select>
            </label>
          </div>
          {loading && <p className="mt-3 text-xs text-gray-500">Loading integration diagnostics…</p>}
          {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
        </section>

        <section className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {visibleConnections.map((connection) => (
            <IntegrationConnectionCard key={connection.integration_id} connection={connection} />
          ))}
          {!loading && visibleConnections.length === 0 && (
            <div className="rounded-lg border border-dashed p-4 text-xs text-gray-500">No integration connections matched these filters.</div>
          )}
        </section>

        <IntegrationHealthTable rows={healthRows} />
        <IntegrationOperationTable rows={filteredOperations} onSelect={setSelected} />
      </div>
      <IntegrationOperationDrawer operation={selected} onClose={() => setSelected(null)} />
    </MainLayout>
  );
}
