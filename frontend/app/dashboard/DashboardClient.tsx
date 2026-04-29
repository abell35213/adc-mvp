"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import MainLayout from "@/components/MainLayout";
import AlertsPanel from "@/components/case-ops/AlertsPanel";
import ExportReadyList from "@/components/case-ops/ExportReadyList";
import IncidentFilterBar, {
  type IncidentFilters,
} from "@/components/case-ops/IncidentFilterBar";
import IncidentQueueTable, {
  type QueueTabKey,
} from "@/components/case-ops/IncidentQueueTable";
import IncidentSummaryCards from "@/components/case-ops/IncidentSummaryCards";
import OverdueFollowUpList from "@/components/case-ops/OverdueFollowUpList";
import SectionCard from "@/components/layout/SectionCard";
import PageHeader from "@/components/layout/PageHeader";
import OnboardingProgressDashboard from "@/components/onboarding/OnboardingProgressDashboard";
import {
  getIntegrationValidationResults,
  getIncidentAlerts,
  getIncidentQueue,
  getIncidentSummaryMetrics,
  getOrgOnboardingQrStats,
  getOrgOnboardingStatus,
  getMyOpenTasks,
  getOverdueTasks,
  patchIncidentOwner,
  patchIncidentStatus,
  toUserErrorMessage,
  type CaseOpsAlerts,
  type CaseOpsQueueItem,
  type CaseOpsSummaryMetrics,
  type CaseStatus,
  type CaseTaskWidgetItem,
  type IntegrationValidationResult,
  type OrgLaunchReadiness,
  type VehicleQrStats,
} from "@/lib/api";
import { ONBOARDING_WIZARD_STORAGE_KEY } from "@/lib/onboarding";
import { useAuth } from "@/lib/useAuth";

const DEFAULT_FILTERS: IncidentFilters = {
  status: "",
  readiness_state: "",
  blockers: "",
  search: "",
  sort: "urgency",
};

const QUEUE_PAGE_SIZE = 50;
const QUEUE_ALL_PAGE_SIZE = 500;

function buildQueueParams(filters: IncidentFilters, includeStatus = true) {
  return {
    ...(includeStatus && filters.status ? { status: filters.status } : {}),
    readiness_state: filters.readiness_state || undefined,
    blockers: filters.blockers || undefined,
    search: filters.search || undefined,
    sort: filters.sort,
    page: 1,
  };
}

const TAB_TO_STATUS: Record<QueueTabKey, string> = {
  all: "",
  new: "new",
  in_review: "in_review",
  awaiting_evidence: "awaiting_evidence",
  ready_for_export: "ready_for_export",
  escalated: "escalated",
  awaiting_follow_up: "awaiting_follow_up",
  exported: "exported",
  closed: "closed",
};

function getFirstPriority(queue: CaseOpsQueueItem[]) {
  return (
    queue.find((item) => item.case_status === "escalated" || item.blockers.critical > 0) ??
    queue.find((item) => item.case_status === "new" || item.blockers.important > 0) ??
    queue[0]
  );
}

export default function DashboardClient() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  // Reactive demo-mode flag: re-evaluates whenever the URL changes (e.g. when
  // updateFilters() calls router.replace) so that the banner stays consistent
  // with what's actually in the URL bar across reloads and navigation.
  const isDemoMode = searchParams?.get("demo") === "1";
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
  const [queueAll, setQueueAll] = useState<CaseOpsQueueItem[]>([]);
  const [metrics, setMetrics] = useState<CaseOpsSummaryMetrics | null>(null);
  const [alerts, setAlerts] = useState<CaseOpsAlerts | null>(null);
  const [overdueTasks, setOverdueTasks] = useState<CaseTaskWidgetItem[]>([]);
  const [myOpenTasks, setMyOpenTasks] = useState<CaseTaskWidgetItem[]>([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [queueError, setQueueError] = useState("");
  const [overviewError, setOverviewError] = useState("");
  const [actionError, setActionError] = useState("");
  const [onboarding, setOnboarding] = useState<OrgLaunchReadiness | null>(null);
  const [qrStats, setQrStats] = useState<VehicleQrStats | null>(null);
  const [integrationValidationResults, setIntegrationValidationResults] = useState<IntegrationValidationResult[]>([]);
  const [demoTourDismissed, setDemoTourDismissed] = useState(false);

  const activeTab = (Object.keys(TAB_TO_STATUS).find(
    (key) => TAB_TO_STATUS[key as QueueTabKey] === filters.status
  ) as QueueTabKey | undefined) ?? "all";

  const resumeOnboardingHref = useMemo(() => {
    if (typeof window === "undefined") return "/onboarding";
    const persistedStep = window.localStorage.getItem(ONBOARDING_WIZARD_STORAGE_KEY);
    return persistedStep
      ? `/onboarding?step=${encodeURIComponent(persistedStep)}`
      : "/onboarding";
  }, []);

  useEffect(() => {
    if (!user) return;

    Promise.all([
      getIncidentQueue({ ...buildQueueParams(filters), page_size: QUEUE_PAGE_SIZE }),
      getIncidentQueue({ ...buildQueueParams(filters, false), page_size: QUEUE_ALL_PAGE_SIZE }),
    ])
      .then(([filtered, unfiltered]) => {
        setQueue(filtered.items);
        setQueueAll(unfiltered.items);
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
      getMyOpenTasks({ limit: 20 }),
    ])
      .then(async ([summary, alertPayload, overdue, mine]) => {
        const onboardingResults = await Promise.allSettled([
          getOrgOnboardingStatus(),
          getOrgOnboardingQrStats(),
          getIntegrationValidationResults(),
        ]);

        setMetrics(summary);
        setAlerts(alertPayload);
        setOverdueTasks(overdue.items);
        setMyOpenTasks(mine.items);
        if (onboardingResults[0].status === "fulfilled") {
          setOnboarding(onboardingResults[0].value);
        } else {
          setOnboarding(null);
        }
        if (onboardingResults[1].status === "fulfilled") {
          setQrStats(onboardingResults[1].value);
        } else {
          setQrStats(null);
        }
        if (onboardingResults[2].status === "fulfilled") {
          setIntegrationValidationResults(onboardingResults[2].value);
        } else {
          setIntegrationValidationResults([]);
        }
        setOverviewError("");
      })
      .catch((err) =>
        setOverviewError(toUserErrorMessage(err, "Failed to load command center"))
      )
      .finally(() => setOverviewLoading(false));
  }, [user]);

  const exportReady = useMemo(
    () => queueAll.filter((item) => item.case_status === "ready_for_export"),
    [queueAll]
  );

  const tabCounts = useMemo(() => {
    const counts: Record<QueueTabKey, number> = {
      all: queueAll.length,
      new: 0,
      in_review: 0,
      awaiting_evidence: 0,
      ready_for_export: 0,
      escalated: 0,
      awaiting_follow_up: 0,
      exported: 0,
      closed: 0,
    };
    for (const item of queueAll) {
      if (item.case_status in counts) {
        counts[item.case_status as QueueTabKey] += 1;
      }
    }

    return [
      { key: "all" as const, label: "All", count: counts.all },
      { key: "new" as const, label: "New", count: counts.new },
      { key: "in_review" as const, label: "In Review", count: counts.in_review },
      { key: "awaiting_evidence" as const, label: "Awaiting Evidence", count: counts.awaiting_evidence },
      { key: "ready_for_export" as const, label: "Ready for Export", count: counts.ready_for_export },
      { key: "escalated" as const, label: "Escalated", count: counts.escalated },
      { key: "awaiting_follow_up" as const, label: "Awaiting Follow-Up", count: counts.awaiting_follow_up },
      { key: "exported" as const, label: "Exported", count: counts.exported },
      { key: "closed" as const, label: "Closed", count: counts.closed },
    ];
  }, [queueAll]);

  const firstPriority = useMemo(() => getFirstPriority(queue), [queue]);
  const firstDemoIncidentId = useMemo<string | null>(() => {
    if (firstPriority?.incident_id) return firstPriority.incident_id;
    if (queueAll.length > 0) return queueAll[0].incident_id;
    return null;
  }, [firstPriority, queueAll]);
  const integrationIssues = integrationValidationResults.filter(
    (result) =>
      result.credentialStatus !== "completed" ||
      result.capabilityStatus !== "completed" ||
      result.mappingStatus !== "completed"
  );
  const onboardingBlockers = onboarding?.blockers ?? [];

  const updateFilters = (next: IncidentFilters) => {
    setFilters(next);
    setQueueLoading(true);
    const query = new URLSearchParams();
    if (next.status) query.set("status", next.status);
    if (next.readiness_state) query.set("readiness_state", next.readiness_state);
    if (next.blockers) query.set("blockers", next.blockers);
    if (next.search) query.set("search", next.search);
    if (next.sort) query.set("sort", next.sort);
    // Preserve the demo flag across in-page URL updates so the tour banner
    // (and any other demo-mode affordances derived from useSearchParams) do
    // not get silently dropped when filters/tabs change.
    if (isDemoMode) query.set("demo", "1");
    const nextUrl = query.toString() ? `/dashboard?${query.toString()}` : "/dashboard";
    router.replace(nextUrl);
  };

  const refreshQueue = () => {
    setQueueLoading(true);
    Promise.all([
      getIncidentQueue({ ...buildQueueParams(filters), page_size: QUEUE_PAGE_SIZE }),
      getIncidentQueue({ ...buildQueueParams(filters, false), page_size: QUEUE_ALL_PAGE_SIZE }),
    ])
      .then(([filtered, unfiltered]) => {
        setQueue(filtered.items);
        setQueueAll(unfiltered.items);
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

  const onCaseStatusChange = async (incidentId: string, caseStatus: CaseStatus) => {
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
        <PageHeader
          eyebrow="Case Operations"
          title="Incident Command Center"
          subtitle="Answer what's new, blocked, ready, and first priority in under 10 seconds."
          actions={(
            <button
              type="button"
              onClick={() => router.push(resumeOnboardingHref)}
              className="rounded border border-status-info/40 bg-status-info-soft px-3 py-1.5 text-sm font-medium text-status-info hover:opacity-90"
            >
              Resume onboarding wizard
            </button>
          )}
          meta={
            firstPriority ? (
              <span>
                First priority: <strong>{firstPriority.incident_id.slice(0, 8)}…</strong> · {firstPriority.blockers.critical} critical blockers · owner {firstPriority.owner_user_id ? firstPriority.owner_user_id.slice(0, 8) : "unassigned"}
              </span>
            ) : (
              "No active incidents in the current queue."
            )
          }
        />

        {isDemoMode && !demoTourDismissed ? (
          <div
            data-testid="demo-tour-banner"
            className="rounded-lg border border-status-info/40 bg-status-info-soft p-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-status-info">
                  Welcome to the ADC demo sandbox
                </p>
                <p className="mt-1 text-sm text-text-secondary">
                  Walk the workflow end-to-end:
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-secondary">
                  <li>
                    Open the seeded incident in the queue below
                    {firstDemoIncidentId ? (
                      <>
                        {" "}—{" "}
                        <button
                          type="button"
                          className="underline hover:text-status-info"
                          onClick={() => router.push(`/incidents/${firstDemoIncidentId}`)}
                        >
                          go to incident
                        </button>
                      </>
                    ) : null}
                  </li>
                  <li>
                    Review export packages on the{" "}
                    <button
                      type="button"
                      className="underline hover:text-status-info"
                      onClick={() => router.push("/exports")}
                    >
                      Exports page
                    </button>
                  </li>
                  <li>
                    Trigger a scenario from the{" "}
                    <button
                      type="button"
                      className="underline hover:text-status-info"
                      onClick={() => router.push("/demo")}
                    >
                      Demo Workspace
                    </button>
                  </li>
                </ul>
              </div>
              <button
                type="button"
                aria-label="Dismiss demo tour"
                className="text-sm text-text-secondary hover:text-text-primary"
                onClick={() => setDemoTourDismissed(true)}
              >
                ✕
              </button>
            </div>
          </div>
        ) : null}

        {overviewError ? <p className="text-sm text-status-critical">{overviewError}</p> : null}
        {actionError ? <p className="text-sm text-status-critical">{actionError}</p> : null}

        <OnboardingProgressDashboard
          readiness={onboarding}
          qrStats={qrStats}
          validationResults={integrationValidationResults}
          loading={overviewLoading}
        />

        <IncidentSummaryCards metrics={metrics} loading={overviewLoading} />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <div className="space-y-4">
            <IncidentFilterBar
              filters={filters}
              onChange={updateFilters}
              onReset={() => updateFilters(DEFAULT_FILTERS)}
            />

            <IncidentQueueTable
              items={queue}
              loading={queueLoading}
              error={queueError}
              tabs={tabCounts}
              activeTab={activeTab}
              onTabChange={(tab) => updateFilters({ ...filters, status: TAB_TO_STATUS[tab] })}
              onOpen={(incidentId) => router.push(`/incidents/${incidentId}`)}
              onAssignMe={onAssignMe}
              onCaseStatusChange={onCaseStatusChange}
            />
          </div>

          <aside className="space-y-4">
            <AlertsPanel alerts={alerts} loading={overviewLoading} error={overviewError} />
            <ExportReadyList items={exportReady} loading={queueLoading} />
            <OverdueFollowUpList
              items={overdueTasks.length > 0 ? overdueTasks : myOpenTasks.filter((task) => task.status !== "completed")}
              loading={overviewLoading}
              error={overviewError}
            />

            <SectionCard
              title="Integration Issues"
              tone="warning"
              description="Integration failures that can block evidence capture."
            >
              {overviewLoading ? <p className="text-sm text-text-secondary">Loading integration validation…</p> : null}
              {!overviewLoading && integrationIssues.length === 0 ? (
                <p className="text-sm text-text-secondary">No active integration issues.</p>
              ) : null}
              {!overviewLoading && integrationIssues.length > 0 ? (
                <ul className="space-y-2 text-sm">
                  {integrationIssues.slice(0, 5).map((result) => (
                    <li key={result.integration_id} className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
                      <p className="font-medium text-text-primary">{result.integration_id}</p>
                      <p className="text-xs text-status-warning">{result.messages[0] ?? "Validation is incomplete."}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </SectionCard>

            <SectionCard
              title="Onboarding Blockers"
              tone="info"
              description="Go-live dependencies not yet completed."
            >
              {overviewLoading ? <p className="text-sm text-text-secondary">Loading onboarding status…</p> : null}
              {!overviewLoading && onboardingBlockers.length === 0 ? (
                <p className="text-sm text-text-secondary">No onboarding blockers.</p>
              ) : null}
              {!overviewLoading && onboardingBlockers.length > 0 ? (
                <ul className="space-y-2 text-sm">
                  {onboardingBlockers.slice(0, 5).map((item) => (
                    <li key={item.code} className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
                      <p className="font-medium text-text-primary">{item.title}</p>
                      <p className="text-xs text-text-secondary">{item.detail}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </SectionCard>
          </aside>
        </div>
      </div>
    </MainLayout>
  );
}
