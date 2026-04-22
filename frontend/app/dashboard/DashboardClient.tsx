"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MainLayout from "@/components/MainLayout";
import AlertsPanel from "@/components/case-ops/AlertsPanel";
import ExportReadyList from "@/components/case-ops/ExportReadyList";
import IncidentFilterBar, {
  type IncidentFilters,
} from "@/components/case-ops/IncidentFilterBar";
import IncidentQueueTable from "@/components/case-ops/IncidentQueueTable";
import IncidentSummaryCards from "@/components/case-ops/IncidentSummaryCards";
import OverdueFollowUpList from "@/components/case-ops/OverdueFollowUpList";
import {
  getIncidentAlerts,
  getIncidentQueue,
  getIncidentSummaryMetrics,
  getOverdueTasks,
  patchIncidentOwner,
  patchIncidentStatus,
  toUserErrorMessage,
  type CaseOpsAlerts,
  type CaseOpsQueueItem,
  type CaseOpsSummaryMetrics,
  type CaseTaskWidgetItem,
} from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

const DEFAULT_FILTERS: IncidentFilters = {
  status: "",
  readiness_state: "",
  blockers: "",
  search: "",
  sort: "urgency",
};

export default function DashboardClient() {
  const { user } = useAuth();
  const router = useRouter();
  const [filters, setFilters] = useState<IncidentFilters>(() => {
    if (typeof window === "undefined") return DEFAULT_FILTERS;
    const params = new URLSearchParams(window.location.search);
    return {
      status: params.get("status") ?? "",
      readiness_state: params.get("readiness_state") ?? "",
      blockers: params.get("blockers") ?? "",
      search: params.get("search") ?? "",
      sort: (params.get("sort") as IncidentFilters["sort"]) ?? "urgency",
    };
  });

  const [queue, setQueue] = useState<CaseOpsQueueItem[]>([]);
  const [metrics, setMetrics] = useState<CaseOpsSummaryMetrics | null>(null);
  const [alerts, setAlerts] = useState<CaseOpsAlerts | null>(null);
  const [overdueTasks, setOverdueTasks] = useState<CaseTaskWidgetItem[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [overviewError, setOverviewError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    if (!user) return;

    getIncidentQueue({
      status: filters.status || undefined,
      readiness_state: filters.readiness_state || undefined,
      blockers: filters.blockers || undefined,
      search: filters.search || undefined,
      sort: filters.sort,
      page: 1,
      page_size: 50,
    })
      .then((payload) => {
        setQueue(payload.items);
        setQueueError("");
      })
      .catch((err) => setQueueError(toUserErrorMessage(err, "Failed to load queue")))
      .finally(() => setQueueLoading(false));
  }, [filters, user]);

  useEffect(() => {
    if (!user) return;

    Promise.all([
      getIncidentSummaryMetrics(),
      getIncidentAlerts(),
      getOverdueTasks({ limit: 20 }),
    ])
      .then(([summary, alertPayload, overdue]) => {
        setMetrics(summary);
        setAlerts(alertPayload);
        setOverdueTasks(overdue.items);
        setOverviewError("");
      })
      .catch((err) =>
        setOverviewError(toUserErrorMessage(err, "Failed to load command center"))
      )
      .finally(() => setOverviewLoading(false));
  }, [user]);

  const exportReady = useMemo(
    () => queue.filter((item) => item.case_status === "ready_for_export"),
    [queue]
  );

  const updateFilters = (next: IncidentFilters) => {
    setFilters(next);
    setQueueLoading(true);
    const query = new URLSearchParams();
    if (next.status) query.set("status", next.status);
    if (next.readiness_state) query.set("readiness_state", next.readiness_state);
    if (next.blockers) query.set("blockers", next.blockers);
    if (next.search) query.set("search", next.search);
    if (next.sort) query.set("sort", next.sort);
    const nextUrl = query.toString() ? `/dashboard?${query.toString()}` : "/dashboard";
    router.replace(nextUrl);
  };

  const refreshQueue = () => {
    setQueueLoading(true);
    getIncidentQueue({
      status: filters.status || undefined,
      readiness_state: filters.readiness_state || undefined,
      blockers: filters.blockers || undefined,
      search: filters.search || undefined,
      sort: filters.sort,
      page: 1,
      page_size: 50,
    })
      .then((payload) => {
        setQueue(payload.items);
        setQueueError("");
      })
      .catch((err) => setQueueError(toUserErrorMessage(err, "Failed to reload queue")))
      .finally(() => setQueueLoading(false));
  };

  const onAssignMe = async (incidentId: string) => {
    if (!user) return;
    try {
      setActionError("");
      await patchIncidentOwner(incidentId, {
        operation: "assign",
        owner_user_id: user.user_id,
      });
      refreshQueue();
    } catch (err) {
      setActionError(toUserErrorMessage(err, "Failed to assign owner"));
    }
  };

  const onCaseStatusChange = async (incidentId: string, caseStatus: string) => {
    try {
      setActionError("");
      await patchIncidentStatus(incidentId, {
        case_status: caseStatus,
        reason: "Updated from command center",
      });
      refreshQueue();
    } catch (err) {
      setActionError(toUserErrorMessage(err, "Failed to change status"));
    }
  };

  return (
    <MainLayout title="Command Center">
      <div className="space-y-4">
        <header>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">Incident Command Center</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Work active incidents, manage ownership, and clear blockers fast.
          </p>
        </header>

        {overviewError ? <p className="text-sm text-red-600">{overviewError}</p> : null}
        {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}

        <IncidentSummaryCards metrics={metrics} loading={overviewLoading} />
        <IncidentFilterBar
          filters={filters}
          onChange={updateFilters}
          onReset={() => updateFilters(DEFAULT_FILTERS)}
        />

        <IncidentQueueTable
          items={queue}
          loading={queueLoading}
          error={queueError}
          onOpen={(incidentId) => router.push(`/incidents/${incidentId}`)}
          onAssignMe={onAssignMe}
          onCaseStatusChange={onCaseStatusChange}
        />

        <div className="grid gap-4 lg:grid-cols-3">
          <AlertsPanel alerts={alerts} loading={overviewLoading} error={overviewError} />
          <ExportReadyList items={exportReady} loading={queueLoading} />
          <OverdueFollowUpList
            items={overdueTasks}
            loading={overviewLoading}
            error={overviewError}
          />
        </div>
      </div>
    </MainLayout>
  );
}
