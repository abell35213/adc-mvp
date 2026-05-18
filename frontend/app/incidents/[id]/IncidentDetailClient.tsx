"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  completeTask,
  createIncidentNote,
  createIncidentTask,
  getDriverProtocolSettings,
  getIncident,
  getIncidentWorkspace,
  listIncidentNotes,
  listIncidentTasks,
  patchIncidentOwner,
  patchIncidentStatus,
  toUserErrorMessage,
  type CaseWorkspaceResponse,
  type CaseStatus,
  type DriverProtocolSummary,
  type DriverResponseSummary,
  type IncidentDetail,
  type IncidentNoteItem,
  type IncidentTaskItem,
} from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import EvidenceTable, { EVIDENCE_TYPES } from "@/components/EvidenceTable";
import Timeline from "@/components/Timeline";
import IncidentDetailExportPanel from "@/components/IncidentDetailExportPanel";
import CaseHeroHeader from "@/components/case-ops/CaseHeroHeader";
import CaseOwnerControl from "@/components/case-ops/CaseOwnerControl";
import CaseStatusControl from "@/components/case-ops/CaseStatusControl";
import CaseReadinessCard, { ExportReadinessBanner } from "@/components/case-ops/CaseReadinessCard";
import EvidenceStatusPanel from "@/components/case-ops/EvidenceStatusPanel";
import MissingItemsPanel from "@/components/case-ops/MissingItemsPanel";
import CaseNotesPanel from "@/components/case-ops/CaseNotesPanel";
import CaseTasksPanel from "@/components/case-ops/CaseTasksPanel";
import TimelineFeed from "@/components/case-ops/TimelineFeed";
import StickySidebar from "@/components/layout/StickySidebar";

function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatWeatherValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toString() : "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value.trim().length > 0 ? value : "—";
  return String(value);
}

function toWeatherMetrics(weather: unknown): Array<{ key: string; value: string }> {
  if (!weather || typeof weather !== "object" || Array.isArray(weather)) return [];

  return Object.entries(weather)
    .filter(([key]) => key.trim().length > 0)
    .map(([key, value]) => ({
      key: key.replaceAll("_", " "),
      value: formatWeatherValue(value),
    }));
}

const REFRESH_INTERVAL_MS = 4000;

export default function IncidentDetailClient() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [driverProtocolSettings, setDriverProtocolSettings] = useState<DriverProtocolSummary | null>(null);
  const [workspace, setWorkspace] = useState<CaseWorkspaceResponse | null>(null);
  const [notes, setNotes] = useState<IncidentNoteItem[]>([]);
  const [tasks, setTasks] = useState<IncidentTaskItem[]>([]);

  const artifactStatuses = useMemo(() => {
    if (!incident) return [];
    const artifactMap = new Map(incident.evidence_inventory.map((artifact) => [artifact.artifact_type, artifact]));
    return EVIDENCE_TYPES.map(({ type }) => artifactMap.get(type)?.status ?? "pending");
  }, [incident]);

  const captured = artifactStatuses.filter((status) => status === "captured").length;
  const unavailable = artifactStatuses.filter((status) => status === "unavailable").length;
  const pending = artifactStatuses.filter((status) => status === "pending").length;
  const total = artifactStatuses.length || EVIDENCE_TYPES.length;
  const isCapturing = pending > 0;
  const refreshIntervalSeconds = REFRESH_INTERVAL_MS / 1000;
  const completenessPercent = incident?.completeness_percent ?? Math.round((captured / total) * 100);

  const refreshIncident = useCallback(() => {
    return getIncident(id)
      .then(setIncident)
      .catch((err) => console.warn("Incident refresh failed", err));
  }, [id]);

  const refreshWorkspacePanels = useCallback(() => {
    return Promise.all([
      getIncidentWorkspace(id).then(setWorkspace),
      listIncidentNotes(id).then((res) => setNotes(res.items)),
      listIncidentTasks(id).then((res) => setTasks(res.items)),
    ]).catch((err) => {
      console.warn("Workspace refresh failed", err);
    });
  }, [id]);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getIncident(id).then(setIncident),
      getIncidentWorkspace(id).then(setWorkspace),
      listIncidentNotes(id).then((res) => setNotes(res.items)),
      listIncidentTasks(id).then((res) => setTasks(res.items)),
    ])
      .catch((err) => setError(toUserErrorMessage(err, "Failed to load incident")))
      .finally(() => setLoading(false));
  }, [id, user]);

  useEffect(() => {
    if (!user) return;
    getDriverProtocolSettings()
      .then((data) => setDriverProtocolSettings(data))
      .catch(() => {
        // Non-admin users may not have access to admin settings.
      });
  }, [user]);

  useEffect(() => {
    if (!user || !isCapturing) return;
    const interval = window.setInterval(() => {
      refreshIncident();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [isCapturing, refreshIncident, user]);

  const captureSummary = isCapturing
    ? `Capture in progress (auto-refreshing every ${refreshIntervalSeconds} seconds).`
    : unavailable > 0
      ? `Capture finished with ${unavailable} unavailable artifact${unavailable === 1 ? "" : "s"}.`
      : "Capture complete.";

  const driverResponse: DriverResponseSummary = incident?.driver_response ?? {};
  const protocolSummary = incident?.driver_protocol_summary ?? driverProtocolSettings;
  const notificationSent = Boolean(driverResponse.notification_sent_at_utc);
  const acknowledged = Boolean(driverResponse.acknowledged_at_utc);
  const uploadsComplete = Boolean(driverResponse.uploads_complete);
  const waitingOnDriver = Boolean(driverResponse.awaiting_driver_action ?? (notificationSent && (!acknowledged || !uploadsComplete)));
  const workspaceCaseStatus = workspace?.case_status ?? "new";
  const workspaceReadiness = workspace?.readiness_state ?? incident?.readiness_state ?? "not_ready";
  const workspaceOwnerUserId = workspace?.owner?.user_id ?? null;
  const workspaceMissingItems = workspace?.missing_items ?? incident?.completeness_missing_items ?? [];
  const workspaceEvidence = workspace?.evidence_summary;
  const workspaceActivity = workspace?.activity ?? [];
  const weatherConditions = incident?.current_weather_conditions;
  const weatherMetrics = toWeatherMetrics(weatherConditions?.normalized_weather);
  const weatherSource = weatherConditions?.raw_source_metadata?.source;
  const weatherCapturedAt = weatherConditions?.raw_source_metadata?.captured_at_utc;
  const weatherLocationSource = incident?.weather_location_source;
  const isLocationUnavailable = weatherLocationSource === "unavailable";
  const isUsingLastKnownLocation = weatherLocationSource === "last_known";
  const isWeatherUnavailable = weatherConditions?.capture_status === "unavailable" || weatherMetrics.length === 0;

  const nextAction = workspaceMissingItems.length > 0
    ? `Collect ${workspaceMissingItems[0]} to unblock readiness.`
    : tasks.find((task) => task.status === "open")?.title ?? "Review export readiness and generate packet.";

  const onAssignMe = useCallback(async () => {
    if (!user) return;
    const previous = workspace;
    setWorkspace((current) => (current ? { ...current, owner: { user_id: user.user_id, email: user.email } } : current));
    try {
      await patchIncidentOwner(id, {
        operation: workspaceOwnerUserId ? "reassign" : "assign",
        owner_user_id: user.user_id,
      });
      await Promise.all([refreshIncident(), refreshWorkspacePanels()]);
    } catch (err) {
      setWorkspace(previous);
      setError(toUserErrorMessage(err, "Failed to assign owner"));
    }
  }, [id, refreshIncident, refreshWorkspacePanels, user, workspace, workspaceOwnerUserId]);

  const onClearOwner = useCallback(async () => {
    const previous = workspace;
    setWorkspace((current) => (current ? { ...current, owner: null } : current));
    try {
      await patchIncidentOwner(id, { operation: "clear" });
      await Promise.all([refreshIncident(), refreshWorkspacePanels()]);
    } catch (err) {
      setWorkspace(previous);
      setError(toUserErrorMessage(err, "Failed to clear owner"));
    }
  }, [id, refreshIncident, refreshWorkspacePanels, workspace]);

  const onCaseStatusChange = useCallback(async (nextStatus: CaseStatus) => {
    const previous = workspace;
    setWorkspace((current) => (current ? { ...current, case_status: nextStatus } : current));
    try {
      await patchIncidentStatus(id, { case_status: nextStatus, reason: "workspace_update" });
      await Promise.all([refreshIncident(), refreshWorkspacePanels()]);
    } catch (err) {
      setWorkspace(previous);
      setError(toUserErrorMessage(err, "Failed to update status"));
    }
  }, [id, refreshIncident, refreshWorkspacePanels, workspace]);

  const onAddNote = useCallback(async (body: string) => {
    const tempNote: IncidentNoteItem = {
      note_id: `temp-${Date.now()}`,
      incident_id: id,
      body,
      note_type: "standard",
      tags: [],
      created_at_utc: new Date().toISOString(),
      edited: false,
      updated_at_utc: new Date().toISOString(),
      is_deleted: false,
    };
    setNotes((current) => [tempNote, ...current]);
    try {
      await createIncidentNote(id, { body, note_type: "standard", tags: [] });
      await refreshWorkspacePanels();
    } catch (err) {
      setNotes((current) => current.filter((note) => note.note_id !== tempNote.note_id));
      setError(toUserErrorMessage(err, "Failed to add note"));
    }
  }, [id, refreshWorkspacePanels]);

  const onAddTask = useCallback(async (title: string) => {
    const tempTask: IncidentTaskItem = {
      task_id: `temp-${Date.now()}`,
      incident_id: id,
      title,
      task_type: "other",
      status: "open",
      priority: "medium",
      overdue: false,
    };
    setTasks((current) => [tempTask, ...current]);
    try {
      await createIncidentTask(id, { title, task_type: "other", priority: "medium" });
      await refreshWorkspacePanels();
    } catch (err) {
      setTasks((current) => current.filter((task) => task.task_id !== tempTask.task_id));
      setError(toUserErrorMessage(err, "Failed to add task"));
    }
  }, [id, refreshWorkspacePanels]);

  const onCompleteTask = useCallback(async (taskId: string) => {
    const previous = tasks;
    setTasks((current) => current.map((task) => (task.task_id === taskId ? { ...task, status: "completed" } : task)));
    try {
      await completeTask(taskId);
      await refreshWorkspacePanels();
    } catch (err) {
      setTasks(previous);
      setError(toUserErrorMessage(err, "Failed to complete task"));
    }
  }, [refreshWorkspacePanels, tasks]);

  if (loading || authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-red-600">{error || "Incident not found"}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto max-w-7xl space-y-6 p-6">
        <CaseHeroHeader
          incidentId={incident.incident_id}
          createdAtLabel={formatTime(incident.created_at_utc)}
          whatHappened={`Severity ${incident.severity ?? "unknown"} incident is currently ${workspaceCaseStatus.replaceAll("_", " ")}.`}
          nextAction={nextAction}
          captured={captured}
          total={total}
          pending={pending}
          unavailable={unavailable}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="space-y-4">
            <EvidenceStatusPanel
              captured={workspaceEvidence?.captured ?? captured}
              pending={workspaceEvidence?.pending ?? pending}
              unavailable={workspaceEvidence?.unavailable ?? unavailable}
              total={workspaceEvidence?.total ?? total}
            />
            <TimelineFeed items={workspaceActivity} />
            <div className="grid gap-4 lg:grid-cols-2">
              <CaseTasksPanel tasks={tasks} onAddTask={onAddTask} onCompleteTask={onCompleteTask} />
              <CaseNotesPanel notes={notes} onAddNote={onAddNote} />
            </div>

            <section className="rounded-lg border bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-600">Weather snapshot</h2>
              <div className="space-y-3 text-sm">
                {isUsingLastKnownLocation ? <p className="text-amber-700">Using last known location</p> : null}
                {isLocationUnavailable ? <p className="text-amber-700">Location unavailable</p> : null}
                {isWeatherUnavailable ? <p className="text-gray-500">Weather data unavailable</p> : null}

                {weatherMetrics.length > 0 ? (
                  <dl className="grid gap-2 sm:grid-cols-2">
                    {weatherMetrics.map((metric) => (
                      <div key={metric.key} className="rounded border border-gray-100 bg-gray-50 px-3 py-2">
                        <dt className="text-xs uppercase tracking-wide text-gray-500">{metric.key}</dt>
                        <dd className="text-sm font-medium text-gray-900">{metric.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}

                <p className="text-xs text-gray-500">Source: {formatWeatherValue(weatherSource)}</p>
                <p className="text-xs text-gray-500">Captured: {formatTime(typeof weatherCapturedAt === "string" ? weatherCapturedAt : null)}</p>
              </div>
            </section>

            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-600">Evidence inventory</h2>
              <p className="mb-4 text-xs text-gray-500">{captureSummary}</p>
              <EvidenceTable artifacts={incident.evidence_inventory} />
            </div>

            <div className="rounded-lg border bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-600">Full timeline</h2>
              <Timeline events={incident.timeline} />
            </div>

            <IncidentDetailExportPanel
              incidentId={id}
              exports={incident.export_status}
              artifacts={incident.evidence_inventory}
              onExportsChanged={refreshIncident}
            />
          </section>

          <StickySidebar className="space-y-4" topOffsetClassName="top-6">
            <CaseOwnerControl ownerUserId={workspaceOwnerUserId} onAssignMe={onAssignMe} onClearOwner={onClearOwner} />
            <CaseStatusControl caseStatus={workspaceCaseStatus} onChange={onCaseStatusChange} />
            <CaseReadinessCard
              readinessState={workspaceReadiness}
              completenessPercent={workspace?.completeness.percent ?? completenessPercent}
              blockersCount={(workspace?.blockers ?? []).length}
            />
            <MissingItemsPanel items={workspaceMissingItems} />
            <ExportReadinessBanner
              blockersCount={(workspace?.blockers ?? []).length}
              readinessState={workspaceReadiness}
              blockers={(workspace?.blockers ?? []) as Array<{ code?: string; message?: string; blocks_readiness?: boolean }>}
            />
            <section className="rounded-lg border bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Driver response</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${waitingOnDriver ? "bg-yellow-100 text-yellow-800" : "bg-green-100 text-green-800"}`}>
                  {waitingOnDriver ? "Waiting on driver action" : "Driver response complete"}
                </span>
              </div>
              {protocolSummary ? (
                <p className="mt-2 text-xs text-gray-500">Protocol: {protocolSummary.instruction_source ?? "default"}</p>
              ) : null}
            </section>
          </StickySidebar>
        </div>
      </main>
    </div>
  );
}
