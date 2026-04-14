"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  completeTask,
  createIncidentNote,
  createIncidentTask,
  getIncident,
  getIncidentWorkspace,
  getDriverProtocolSettings,
  listIncidentNotes,
  listIncidentTasks,
  type IncidentDetail,
  type IncidentNoteItem,
  type IncidentTaskItem,
  type CaseWorkspaceResponse,
  type DriverProtocolSummary,
  type DriverResponseSummary,
  patchIncidentOwner,
  patchIncidentStatus,
  toUserErrorMessage,
} from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import EvidenceTable, { EVIDENCE_TYPES } from "@/components/EvidenceTable";
import Timeline from "@/components/Timeline";
import IncidentDetailExportPanel from "@/components/IncidentDetailExportPanel";
import CaseOwnerControl from "@/components/case-ops/CaseOwnerControl";
import CaseStatusControl from "@/components/case-ops/CaseStatusControl";
import CaseReadinessCard, { ExportReadinessBanner } from "@/components/case-ops/CaseReadinessCard";
import EvidenceStatusPanel from "@/components/case-ops/EvidenceStatusPanel";
import MissingItemsPanel from "@/components/case-ops/MissingItemsPanel";
import CaseNotesPanel from "@/components/case-ops/CaseNotesPanel";
import CaseTasksPanel from "@/components/case-ops/CaseTasksPanel";
import TimelineFeed from "@/components/case-ops/TimelineFeed";

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

const REFRESH_INTERVAL_MS = 4000;

export default function IncidentDetailClient() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [driverProtocolSettings, setDriverProtocolSettings] =
    useState<DriverProtocolSummary | null>(null);
  const [workspace, setWorkspace] = useState<CaseWorkspaceResponse | null>(null);
  const [notes, setNotes] = useState<IncidentNoteItem[]>([]);
  const [tasks, setTasks] = useState<IncidentTaskItem[]>([]);

  const artifactStatuses = useMemo(() => {
    if (!incident) return [];
    const artifactMap = new Map(
      incident.evidence_inventory.map((artifact) => [
        artifact.artifact_type,
        artifact,
      ])
    );
    return EVIDENCE_TYPES.map(
      ({ type }) => artifactMap.get(type)?.status ?? "pending"
    );
  }, [incident]);

  const captured = artifactStatuses.filter((status) => status === "captured")
    .length;
  const unavailable = artifactStatuses.filter(
    (status) => status === "unavailable"
  ).length;
  const pending = artifactStatuses.filter((status) => status === "pending")
    .length;
  const total = artifactStatuses.length || EVIDENCE_TYPES.length;
  const isCapturing = pending > 0;
  const refreshIntervalSeconds = REFRESH_INTERVAL_MS / 1000;
  const timelineTypes = useMemo(
    () => new Set((incident?.timeline ?? []).map((event) => event.event_type)),
    [incident]
  );
  const lifecycleCoverage = useMemo(() => {
    const hasCollected = [...timelineTypes].some(
      (type) =>
        type.includes("capture") ||
        type.includes("collected") ||
        type.includes("incident_started")
    );
    const hasValidated = [...timelineTypes].some(
      (type) => type.includes("hash") || type.includes("validat")
    );
    const hasExported = [...timelineTypes].some((type) => type.includes("export"));
    const hasDownloaded = [...timelineTypes].some((type) =>
      type.includes("download")
    );
    return { hasCollected, hasValidated, hasExported, hasDownloaded };
  }, [timelineTypes]);
  const completenessPercent =
    incident?.completeness_percent ?? Math.round((captured / total) * 100);
  const continuityChecks = [
    lifecycleCoverage.hasCollected,
    lifecycleCoverage.hasValidated,
    lifecycleCoverage.hasExported,
  ].filter(Boolean).length;
  const custodyContinuityLabel =
    continuityChecks === 3
      ? "Strong"
      : continuityChecks === 2
        ? "Partial"
        : "Limited";

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
      ? `Capture finished with ${unavailable} unavailable artifact${
          unavailable === 1 ? "" : "s"
        }.`
      : "Capture complete.";

  const driverResponse: DriverResponseSummary = incident?.driver_response ?? {};
  const protocolSummary =
    incident?.driver_protocol_summary ?? driverProtocolSettings;
  const notificationSent = Boolean(driverResponse.notification_sent_at_utc);
  const acknowledged = Boolean(driverResponse.acknowledged_at_utc);
  const uploadsComplete = Boolean(driverResponse.uploads_complete);
  const waitingOnDriver = Boolean(
    driverResponse.awaiting_driver_action ??
      (notificationSent && (!acknowledged || !uploadsComplete))
  );
  const workspaceCaseStatus = workspace?.case_status ?? incident?.status ?? "new";
  const workspaceReadiness = workspace?.readiness_state ?? incident?.readiness_state ?? "not_ready";
  const workspaceOwnerUserId = workspace?.owner?.user_id ?? null;
  const workspaceMissingItems = workspace?.missing_items ?? incident?.completeness_missing_items ?? [];
  const workspaceEvidence = workspace?.evidence_summary;
  const workspaceActivity = workspace?.activity ?? [];

  const onAssignMe = useCallback(async () => {
    if (!user) return;
    const previous = workspace;
    setWorkspace((current) =>
      current
        ? { ...current, owner: { user_id: user.user_id, email: user.email } }
        : current
    );
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

  const onCaseStatusChange = useCallback(async (nextStatus: string) => {
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
    setTasks((current) =>
      current.map((task) => (task.task_id === taskId ? { ...task, status: "completed" } : task))
    );
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-6 py-4 dark:bg-gray-800">
        <div className="flex items-center gap-4">
          <Link
            href="/incidents"
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            ← Incidents
          </Link>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">
            Incident {incident.incident_id.slice(0, 8)}…
          </h1>
          <span className="text-xs text-gray-400">
            {formatTime(incident.created_at_utc)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-green-100 px-2 py-0.5 font-medium text-green-800">
            Captured {captured}/{total}
          </span>
          {pending > 0 && (
            <span className="rounded-full bg-yellow-100 px-2 py-0.5 font-medium text-yellow-800">
              Pending {pending}
            </span>
          )}
          {unavailable > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 font-medium text-red-800">
              Unavailable {unavailable}
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 p-6">
        <div className="rounded-lg border bg-white p-4 shadow dark:bg-gray-800">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Defensibility Summary
          </h2>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded border bg-gray-50 p-3 dark:bg-gray-700">
              <p className="text-xs text-gray-500">Artifact Completeness</p>
              <p className="font-semibold text-gray-900 dark:text-white">
                {captured}/{total} ({completenessPercent}%)
              </p>
            </div>
            <div className="rounded border bg-gray-50 p-3 dark:bg-gray-700">
              <p className="text-xs text-gray-500">Custody Continuity</p>
              <p className="font-semibold text-gray-900 dark:text-white">
                {custodyContinuityLabel}
              </p>
            </div>
            <div className="rounded border bg-gray-50 p-3 dark:bg-gray-700">
              <p className="text-xs text-gray-500">Unavailable Artifacts</p>
              <p className="font-semibold text-gray-900 dark:text-white">
                {unavailable}
              </p>
            </div>
            <div className="rounded border bg-gray-50 p-3 dark:bg-gray-700">
              <p className="text-xs text-gray-500">Readiness State</p>
              <p className="font-semibold text-gray-900 capitalize dark:text-white">
                {(incident.readiness_state ?? "not_ready").replaceAll("_", " ")}
              </p>
            </div>
            <div className="rounded border bg-gray-50 p-3 dark:bg-gray-700">
              <p className="text-xs text-gray-500">Lifecycle Coverage</p>
              <p className="font-semibold text-gray-900 dark:text-white">
                {lifecycleCoverage.hasCollected ? "✓C " : "•C "}
                {lifecycleCoverage.hasValidated ? "✓V " : "•V "}
                {lifecycleCoverage.hasExported ? "✓E " : "•E "}
                {lifecycleCoverage.hasDownloaded ? "✓D" : "•D"}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <CaseOwnerControl
            ownerUserId={workspaceOwnerUserId}
            onAssignMe={onAssignMe}
            onClearOwner={onClearOwner}
          />
          <CaseStatusControl caseStatus={workspaceCaseStatus} onChange={onCaseStatusChange} />
          <CaseReadinessCard
            readinessState={workspaceReadiness}
            completenessPercent={workspace?.completeness.percent ?? completenessPercent}
            blockersCount={(workspace?.blockers ?? []).length}
          />
        </div>

        <ExportReadinessBanner
          blockersCount={(workspace?.blockers ?? []).length}
          readinessState={workspaceReadiness}
          blockers={(workspace?.blockers ?? []) as Array<{ code?: string; message?: string; blocks_readiness?: boolean }>}
        />
        <EvidenceStatusPanel
          captured={workspaceEvidence?.captured ?? captured}
          pending={workspaceEvidence?.pending ?? pending}
          unavailable={workspaceEvidence?.unavailable ?? unavailable}
          total={workspaceEvidence?.total ?? total}
        />
        <MissingItemsPanel items={workspaceMissingItems} />
        <div className="grid gap-4 lg:grid-cols-2">
          <CaseNotesPanel notes={notes} onAddNote={onAddNote} />
          <CaseTasksPanel tasks={tasks} onAddTask={onAddTask} onCompleteTask={onCompleteTask} />
        </div>
        <TimelineFeed items={workspaceActivity} />

        {/* ── Panel A: Evidence Inventory ────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            A) Evidence Inventory
          </h2>
          <p className="mb-4 text-xs text-gray-500">{captureSummary}</p>
          <EvidenceTable artifacts={incident.evidence_inventory} />
        </div>

        {/* ── Panel B: Timeline ──────────────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            B) Timeline
          </h2>
          <Timeline events={incident.timeline} />
        </div>

        {/* ── Panel C: Export Actions ────────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            C) Export Actions
          </h2>
          <IncidentDetailExportPanel
            incidentId={id}
            exports={incident.export_status}
            artifacts={incident.evidence_inventory}
            onExportsChanged={refreshIncident}
          />
        </div>

        {/* ── Panel D: Driver Response ───────────────────────────── */}
        <div className="rounded-lg border bg-white p-6 shadow dark:bg-gray-800">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
            D) Driver response
          </h2>
          <div className="mb-4 flex flex-wrap gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                waitingOnDriver
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-green-100 text-green-800"
              }`}
            >
              {waitingOnDriver
                ? "Waiting on driver action"
                : "Driver response complete"}
            </span>
          </div>
          <ul className="space-y-3 text-sm text-gray-700 dark:text-gray-200">
            <li className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
              <span>Notification sent</span>
              <span className={notificationSent ? "text-green-700" : "text-gray-500"}>
                {notificationSent
                  ? formatTime(driverResponse.notification_sent_at_utc)
                  : "Pending"}
              </span>
            </li>
            <li className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
              <span>Acknowledged</span>
              <span className={acknowledged ? "text-green-700" : "text-gray-500"}>
                {acknowledged ? formatTime(driverResponse.acknowledged_at_utc) : "Pending"}
              </span>
            </li>
            <li className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
              <span>Uploads complete</span>
              <span className={uploadsComplete ? "text-green-700" : "text-gray-500"}>
                {uploadsComplete
                  ? formatTime(driverResponse.uploads_completed_at_utc)
                  : "Pending"}
              </span>
            </li>
          </ul>

          {protocolSummary && (
            <div className="mt-6 rounded-md border bg-gray-50 p-4 dark:bg-gray-900/40">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Driver protocol configuration
              </h3>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-gray-500">Instruction source</dt>
                  <dd className="font-medium capitalize text-gray-800 dark:text-gray-200">
                    {protocolSummary.instruction_source ?? "Default"}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">Acknowledgment required</dt>
                  <dd className="font-medium text-gray-800 dark:text-gray-200">
                    {protocolSummary.require_ack ? "Yes" : "No"}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">SMS notifications</dt>
                  <dd className="font-medium text-gray-800 dark:text-gray-200">
                    {protocolSummary.sms_enabled ? "Enabled" : "Disabled"}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">Voice notifications</dt>
                  <dd className="font-medium text-gray-800 dark:text-gray-200">
                    {protocolSummary.voice_enabled ? "Enabled" : "Disabled"}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
