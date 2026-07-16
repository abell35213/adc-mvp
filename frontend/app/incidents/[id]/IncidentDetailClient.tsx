"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import MainLayout from "@/components/layout/MainLayout";
import IncidentDetailExportPanel from "@/components/IncidentDetailExportPanel";
import CaseOwnerControl from "@/components/case-ops/CaseOwnerControl";
import CaseStatusControl from "@/components/case-ops/CaseStatusControl";
import { Alert, Button, Card, CardContent, CardHeader, DropdownMenu, EmptyState, ProgressBar, Skeleton, StatusBadge, Tabs } from "@/components/ui";
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
  type CaseStatus,
  type CaseWorkspaceResponse,
  type DriverProtocolSummary,
  type DriverResponseSummary,
  type IncidentDetail,
  type IncidentNoteItem,
  type IncidentTaskItem,
} from "@/lib/api";
import { buildIncidentWorkspaceViewModel, formatDateTime, humanize, type WorkspaceTab } from "@/lib/incident-workspace/viewModel";
import { useAuth } from "@/lib/useAuth";

const REFRESH_INTERVAL_MS = 4000;
const TABS: { id: WorkspaceTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "timeline", label: "Timeline" },
  { id: "documents", label: "Documents" },
  { id: "activity", label: "Activity" },
];

function copyText(value: string) { void navigator.clipboard?.writeText(value); }

function formatTime(iso?: string | null): string { return formatDateTime(iso); }

function formatWeatherValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toString() : "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value.trim().length > 0 ? value : "—";
  if (Array.isArray(value)) return value.map((item) => formatWeatherValue(item)).filter((item) => item !== "—").join(", ") || "—";
  return "—";
}

function toWeatherMetrics(weather: unknown): Array<{ key: string; value: string }> {
  if (!weather || typeof weather !== "object" || Array.isArray(weather)) return [];
  return Object.entries(weather).map(([key, value]) => ({ key: key.replaceAll("_", " "), value: formatWeatherValue(value) }));
}

function TechnicalDetails({ incident }: { incident: IncidentDetail }) {
  return (
    <details className="rounded-md border border-border-subtle bg-surface-subtle p-3 text-xs text-text-secondary">
      <summary className="cursor-pointer font-medium text-text-primary">View technical details</summary>
      <dl className="mt-3 grid gap-2">
        <div><dt className="font-medium">Incident ID</dt><dd className="break-all font-mono">{incident.incident_id}</dd></div>
        <div><dt className="font-medium">Driver ID</dt><dd className="break-all font-mono">{incident.adc_driver_id ?? "—"}</dd></div>
        <div><dt className="font-medium">Vehicle ID</dt><dd className="break-all font-mono">{incident.adc_vehicle_id ?? incident.samsara_vehicle_id ?? "—"}</dd></div>
      </dl>
    </details>
  );
}

export default function IncidentDetailClient() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading: authLoading } = useAuth();
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [driverProtocolSettings, setDriverProtocolSettings] = useState<DriverProtocolSummary | null>(null);
  const [workspace, setWorkspace] = useState<CaseWorkspaceResponse | null>(null);
  const [notes, setNotes] = useState<IncidentNoteItem[]>([]);
  const [tasks, setTasks] = useState<IncidentTaskItem[]>([]);
  const [mutationError, setMutationError] = useState("");
  const rawTab = searchParams.get("tab");
  const selectedTab: WorkspaceTab =
    rawTab && TABS.some((tab) => tab.id === rawTab) ? (rawTab as WorkspaceTab) : "overview";

  const artifactStatuses = useMemo(() => incident?.evidence_inventory.map((artifact) => artifact.status) ?? [], [incident]);
  const isCapturing = artifactStatuses.some((status) => status === "pending");

  const refreshIncident = useCallback(() => getIncident(id).then(setIncident).catch((err) => console.warn("Incident refresh failed", err)), [id]);
  const refreshWorkspacePanels = useCallback(() => Promise.all([
    getIncidentWorkspace(id).then(setWorkspace),
    listIncidentNotes(id).then((res) => setNotes(res.items)),
    listIncidentTasks(id).then((res) => setTasks(res.items)),
  ]).catch((err) => console.warn("Workspace refresh failed", err)), [id]);

  useEffect(() => {
    if (!user) return;
    Promise.all([
      getIncident(id).then(setIncident),
      getIncidentWorkspace(id).then(setWorkspace),
      listIncidentNotes(id).then((res) => setNotes(res.items)),
      listIncidentTasks(id).then((res) => setTasks(res.items)),
    ]).catch((err) => setError(toUserErrorMessage(err, "Failed to load incident"))).finally(() => setLoading(false));
  }, [id, user]);

  useEffect(() => { if (!user) return; getDriverProtocolSettings().then(setDriverProtocolSettings).catch(() => undefined); }, [user]);
  useEffect(() => { if (!user || !isCapturing) return; const interval = window.setInterval(refreshIncident, REFRESH_INTERVAL_MS); return () => window.clearInterval(interval); }, [isCapturing, refreshIncident, user]);

  const view = useMemo(() => incident ? buildIncidentWorkspaceViewModel({ incident, workspace, notes, tasks }) : null, [incident, notes, tasks, workspace]);

  const changeTab = (tab: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`/incidents/${id}?${params.toString()}`, { scroll: false });
  };

  const onAssignMe = useCallback(async () => {
    if (!user) return;
    const previous = workspace;
    setMutationError("");
    setWorkspace((current) => (current ? { ...current, owner: { user_id: user.user_id, email: user.email } } : current));
    try { await patchIncidentOwner(id, { operation: workspace?.owner?.user_id ? "reassign" : "assign", owner_user_id: user.user_id }); await Promise.all([refreshIncident(), refreshWorkspacePanels()]); }
    catch (err) { setWorkspace(previous); setMutationError(toUserErrorMessage(err, "Failed to assign owner")); }
  }, [id, refreshIncident, refreshWorkspacePanels, user, workspace]);

  const onClearOwner = useCallback(async () => {
    const previous = workspace;
    setMutationError("");
    setWorkspace((current) => (current ? { ...current, owner: null } : current));
    try { await patchIncidentOwner(id, { operation: "clear" }); await Promise.all([refreshIncident(), refreshWorkspacePanels()]); }
    catch (err) { setWorkspace(previous); setMutationError(toUserErrorMessage(err, "Failed to clear owner")); }
  }, [id, refreshIncident, refreshWorkspacePanels, workspace]);

  const onCaseStatusChange = useCallback(async (nextStatus: CaseStatus) => {
    const previous = workspace;
    setMutationError("");
    setWorkspace((current) => (current ? { ...current, case_status: nextStatus } : current));
    try { await patchIncidentStatus(id, { case_status: nextStatus, reason: "workspace_update" }); await Promise.all([refreshIncident(), refreshWorkspacePanels()]); }
    catch (err) { setWorkspace(previous); setMutationError(toUserErrorMessage(err, "Failed to update status")); }
  }, [id, refreshIncident, refreshWorkspacePanels, workspace]);

  const onAddNote = useCallback(async (body: string) => {
    const tempNote: IncidentNoteItem = { note_id: `temp-${Date.now()}`, incident_id: id, body, note_type: "standard", tags: [], created_at_utc: new Date().toISOString(), edited: false, updated_at_utc: new Date().toISOString(), is_deleted: false };
    setNotes((current) => [tempNote, ...current]);
    try { await createIncidentNote(id, { body, note_type: "standard", tags: [] }); await refreshWorkspacePanels(); }
    catch (err) { setNotes((current) => current.filter((note) => note.note_id !== tempNote.note_id)); setMutationError(toUserErrorMessage(err, "Failed to add note")); }
  }, [id, refreshWorkspacePanels]);

  const onAddTask = useCallback(async (title: string) => {
    const tempTask: IncidentTaskItem = { task_id: `temp-${Date.now()}`, incident_id: id, title, task_type: "other", status: "open", priority: "medium", overdue: false };
    setTasks((current) => [tempTask, ...current]);
    try { await createIncidentTask(id, { title, task_type: "other", priority: "medium" }); await refreshWorkspacePanels(); }
    catch (err) { setTasks((current) => current.filter((task) => task.task_id !== tempTask.task_id)); setMutationError(toUserErrorMessage(err, "Failed to add task")); }
  }, [id, refreshWorkspacePanels]);

  const onCompleteTask = useCallback(async (taskId: string) => {
    const previous = tasks;
    setTasks((current) => current.map((task) => (task.task_id === taskId ? { ...task, status: "completed" } : task)));
    try { await completeTask(taskId); await refreshWorkspacePanels(); }
    catch (err) { setTasks(previous); setMutationError(toUserErrorMessage(err, "Failed to complete task")); }
  }, [refreshWorkspacePanels, tasks]);

  if (loading || authLoading) return <MainLayout title="Incident workspace"><div className="space-y-4"><Skeleton className="h-44"/><Skeleton className="h-96"/></div></MainLayout>;
  if (error || !incident || !view) return <MainLayout title="Incident workspace"><Alert tone="critical" title="Incident unavailable" description={error || "Incident not found or you do not have access."} /></MainLayout>;

  const driverResponse: DriverResponseSummary = incident.driver_response ?? {};
  const waitingOnDriver = Boolean(driverResponse.awaiting_driver_action ?? (driverResponse.notification_sent_at_utc && (!driverResponse.acknowledged_at_utc || !driverResponse.uploads_complete)));

  return (
    <MainLayout title={view.caseReference}>
      <div className="space-y-6">
        <header className="rounded-xl border border-border-default bg-surface p-6 shadow-bordered">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-3"><h1 className="text-3xl font-semibold tracking-tight text-text-primary">{view.caseReference}</h1><StatusBadge tone={view.statusTone}>{view.statusLabel}</StatusBadge></div>
              <p className="text-xl font-medium text-text-primary">{view.title}</p>
              <p className="text-sm text-text-secondary"><time dateTime={view.createdAbsolute}>{view.createdLabel}</time> · {view.location}</p>
              <p className="text-sm text-text-secondary">Owner: <span className="font-medium text-text-primary">{view.ownerLabel}</span> · Last updated: <span title={formatDateTime(view.createdAbsolute)}>{view.updatedLabel}</span></p>
              <div className="max-w-xl"><ProgressBar value={view.readinessPercent} label={`Evidence readiness: ${view.readinessPercent}%`} tone={view.readinessTone} /></div>
            </div>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <Button onClick={() => view.nextAction.kind === "missing_evidence" ? changeTab("evidence") : view.nextAction.kind === "download" || view.nextAction.kind === "generate" ? changeTab("documents") : changeTab("overview")}>{view.nextAction.label}</Button>
              <DropdownMenu label="More actions" items={[{ label: "Copy case ID", onSelect: () => copyText(incident.incident_id) }, { label: "View documents", onSelect: () => changeTab("documents") }, { label: "View technical details", onSelect: () => changeTab("overview") }]} />
            </div>
          </div>
        </header>

        {mutationError ? <Alert tone="critical" title="Update failed" description={mutationError} /> : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-5">
            <Tabs items={TABS} activeId={selectedTab} onChange={changeTab} label="Incident workspace sections" />

            {selectedTab === "overview" ? <OverviewTab view={view} incident={incident} waitingOnDriver={waitingOnDriver} protocol={driverProtocolSettings?.instruction_source} /> : null}
            {selectedTab === "evidence" ? <EvidenceTab view={view} /> : null}
            {selectedTab === "timeline" ? <TimelineTab view={view} /> : null}
            {selectedTab === "documents" ? <DocumentsTab incident={incident} onRefresh={refreshIncident} /> : null}
            {selectedTab === "activity" ? <ActivityTab view={view} onAddNote={onAddNote} onAddTask={onAddTask} onCompleteTask={onCompleteTask} /> : null}
          </div>

          <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start" aria-label="Case action rail">
            <Card><CardHeader title="Next best action" description={view.nextAction.reason}/><CardContent><Button fullWidth onClick={() => view.nextAction.kind === "missing_evidence" ? changeTab("evidence") : view.nextAction.kind === "download" || view.nextAction.kind === "generate" ? changeTab("documents") : changeTab("overview")}>{view.nextAction.label}</Button></CardContent></Card>
            <Card><CardHeader title="Missing items"/><CardContent>{view.missingItems.length === 0 ? <EmptyState title="No missing evidence" message="No readiness-required missing items are currently reported."/> : <ul className="space-y-2 text-sm text-text-secondary">{view.missingItems.slice(0,4).map((item) => <li key={item}>• {item}</li>)}</ul>}</CardContent></Card>
            <CaseOwnerControl ownerUserId={workspace?.owner?.user_id} onAssignMe={onAssignMe} onClearOwner={onClearOwner} />
            <CaseStatusControl caseStatus={workspace?.case_status ?? "new"} onChange={onCaseStatusChange} />
            <TechnicalDetails incident={incident} />
          </aside>
        </div>
      </div>
    </MainLayout>
  );
}

function OverviewTab({ view, incident, waitingOnDriver, protocol }: { view: NonNullable<ReturnType<typeof buildIncidentWorkspaceViewModel>>; incident: IncidentDetail; waitingOnDriver: boolean; protocol?: string | null }) {
  const blockerCount = view.blockers.critical.length + view.blockers.important.length + view.blockers.recommended.length;
  const weatherConditions = incident.current_weather_conditions;
  const weatherMetrics = toWeatherMetrics(weatherConditions?.normalized_weather);
  const weatherSource = weatherConditions?.location?.source;
  const weatherCapturedAt = incident.timeline?.filter((event) => event.event_type === "weather_snapshot_captured").map((event) => event.occurred_at_utc).reverse().find((occurredAt): occurredAt is string => typeof occurredAt === "string" && occurredAt.length > 0) ?? null;
  const weatherLocationSource = incident.weather_location_source;
  const isLocationUnavailable = weatherLocationSource === "unavailable";
  const isUsingLastKnownLocation = weatherLocationSource === "eld_last_known";
  const isWeatherUnavailable = weatherConditions?.capture_status === "unavailable" || weatherMetrics.length === 0;
  return <div className="grid gap-5"><Card><CardHeader title="Incident summary"/><CardContent><p className="text-sm text-text-secondary">{view.narrative}</p><dl className="mt-4 grid gap-3 sm:grid-cols-2"><Info label="Date/time" value={view.createdLabel}/><Info label="Location" value={view.location}/><Info label="Status" value={view.statusLabel}/><Info label="Readiness" value={`${view.readinessPercent}% · ${view.readinessLabel}`}/></dl></CardContent></Card><Card><CardHeader title="Driver and vehicle"/><CardContent><dl className="grid gap-3 sm:grid-cols-2"><Info label="Driver" value={view.driverLabel}/><Info label="Vehicle" value={view.vehicleLabel}/><Info label="Driver response" value={waitingOnDriver ? "Waiting on driver action" : "Driver response complete"}/><Info label="Protocol" value={protocol ?? "Default protocol"}/></dl></CardContent></Card><Card><CardHeader title="Weather snapshot"/><CardContent>{isUsingLastKnownLocation ? <p className="text-sm text-text-secondary">Using last known location</p> : null}{isLocationUnavailable ? <p className="text-sm text-text-secondary">Location unavailable</p> : null}{isWeatherUnavailable ? <p className="text-sm text-text-secondary">Weather data unavailable</p> : null}{weatherMetrics.length > 0 ? (<dl className="mt-3 grid gap-2 sm:grid-cols-2">{weatherMetrics.map((metric) => (<Info key={metric.key} label={metric.key} value={metric.value}/>))}</dl>) : null}<p className="mt-3 text-xs text-text-muted">Source: {formatWeatherValue(weatherSource)}</p><p className="text-xs text-text-muted">Captured: {formatTime(typeof weatherCapturedAt === "string" ? weatherCapturedAt : null)}</p></CardContent></Card><Card><CardHeader title="Evidence inventory" description="Summary of collected and missing evidence appears on the Evidence tab."/><CardContent><p className="text-sm text-text-secondary">Use the Evidence tab to review artifact status, availability notes, and missing items.</p></CardContent></Card><Card><CardHeader title="Key risks and missing information"/><CardContent>{blockerCount === 0 && view.missingItems.length === 0 ? <EmptyState title="No active blockers" message="The workspace has no active readiness blockers."/> : <div className="space-y-4"><BlockerList title="Critical" items={view.blockers.critical}/><BlockerList title="Important" items={view.blockers.important}/>{view.missingItems.length ? <div><h3 className="text-sm font-semibold text-text-primary">Missing information</h3><ul className="mt-2 list-disc pl-5 text-sm text-text-secondary">{view.missingItems.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}</div>}</CardContent></Card><Card><CardHeader title="Recommended next action" description={view.nextAction.reason} actions={<Button>{view.nextAction.label}</Button>}/></Card><TechnicalDetails incident={incident}/></div>;
}

function EvidenceTab({ view }: { view: NonNullable<ReturnType<typeof buildIncidentWorkspaceViewModel>> }) { return <div className="space-y-5">{view.evidenceGroups.map((group) => <Card key={group.id}><CardHeader title={group.title} description="Evidence status is grouped by currently supported ADC artifact types."/><CardContent>{group.items.length === 0 ? <EmptyState title="No evidence" message="No evidence artifacts have been recorded."/> : <div className="grid gap-3 md:grid-cols-2">{group.items.map((item) => <article key={item.id} className="rounded-lg border border-border-subtle p-4"><div className="flex items-start justify-between gap-3"><h3 className="font-medium text-text-primary">{item.label}</h3><StatusBadge tone={item.statusTone}>{humanize(item.status)}</StatusBadge></div><dl className="mt-3 space-y-1 text-sm text-text-secondary"><Info label="Source" value={item.source}/><Info label="Received" value={item.capturedAt}/><Info label="Detail" value={item.detail}/></dl></article>)}</div>}</CardContent></Card>)}</div>; }
function TimelineTab({ view }: { view: NonNullable<ReturnType<typeof buildIncidentWorkspaceViewModel>> }) { return <Card><CardHeader title="Chronological timeline" description="Newest activity is shown first. Technical payloads are available in each disclosure."/><CardContent>{view.timelineItems.length === 0 ? <EmptyState title="No timeline activity" message="No case timeline events have been recorded."/> : <ol className="space-y-4">{view.timelineItems.map((item) => <li key={item.id} className="border-l-2 border-border-subtle pl-4"><time className="text-xs text-text-muted" dateTime={item.absolute}>{item.timestamp}</time><h3 className="text-sm font-semibold text-text-primary">{item.title}</h3><p className="text-sm text-text-secondary">{item.actor} · {item.description}</p><details className="mt-2 text-xs"><summary className="cursor-pointer text-text-link">View technical details</summary><pre className="mt-2 overflow-auto rounded bg-surface-subtle p-3 text-text-secondary">{item.technical}</pre></details></li>)}</ol>}</CardContent></Card>; }
function DocumentsTab({ incident, onRefresh }: { incident: IncidentDetail; onRefresh: () => Promise<void> }) { return <Card><CardHeader title="Documents and defense packets" description="Generate, retry, and download supported packet exports."/><CardContent><IncidentDetailExportPanel incidentId={incident.incident_id} exports={incident.export_status} artifacts={incident.evidence_inventory} onExportsChanged={onRefresh}/></CardContent></Card>; }
function ActivityTab({ view, onAddNote, onAddTask, onCompleteTask }: { view: NonNullable<ReturnType<typeof buildIncidentWorkspaceViewModel>>; onAddNote: (body: string) => Promise<void>; onAddTask: (title: string) => Promise<void>; onCompleteTask: (id: string) => Promise<void> }) { const [note, setNote] = useState(""); const [task, setTask] = useState(""); return <div className="space-y-5"><Card><CardHeader title="Case notes and tasks" description="Human collaboration is separated from the system timeline."/><CardContent><div className="grid gap-3 sm:grid-cols-2"><form onSubmit={(e) => { e.preventDefault(); if (!note.trim()) return; void onAddNote(note.trim()); setNote(""); }} className="space-y-2"><label className="text-sm font-medium text-text-primary">Add note<textarea value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 min-h-24 w-full rounded-md border border-border-default p-2"/></label><Button type="submit" variant="secondary">Add note</Button></form><form onSubmit={(e) => { e.preventDefault(); if (!task.trim()) return; void onAddTask(task.trim()); setTask(""); }} className="space-y-2"><label className="text-sm font-medium text-text-primary">Add task<input value={task} onChange={(e) => setTask(e.target.value)} className="mt-1 w-full rounded-md border border-border-default p-2"/></label><Button type="submit" variant="secondary">Add task</Button></form></div></CardContent></Card><Card><CardHeader title="Recent collaboration"/><CardContent>{view.activityItems.length === 0 ? <EmptyState title="No activity" message="No notes or tasks have been added yet."/> : <ul className="space-y-3">{view.activityItems.map((item) => <li key={item.id} className="rounded-lg border border-border-subtle p-3"><div className="flex justify-between gap-3"><h3 className="text-sm font-semibold text-text-primary">{item.title}</h3><time className="text-xs text-text-muted">{item.timestamp}</time></div><p className="mt-1 text-sm text-text-secondary">{item.body}</p><p className="mt-1 text-xs text-text-muted">{item.actor}</p>{item.body.includes("Open") ? <Button size="sm" variant="quiet" onClick={() => onCompleteTask(item.id)}>Mark complete</Button> : null}</li>)}</ul>}</CardContent></Card></div>; }
function Info({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</dt><dd className="mt-1 text-sm text-text-primary">{value}</dd></div>; }
function BlockerList({ title, items }: { title: string; items: Array<{ code?: string; message?: string; actionHint?: string }> }) { if (items.length === 0) return null; return <div><h3 className="text-sm font-semibold text-text-primary">{title}</h3><ul className="mt-2 space-y-2">{items.map((item, index) => <li key={`${item.code ?? title}-${index}`} className="rounded-md border border-border-subtle p-3 text-sm text-text-secondary"><span className="font-medium text-text-primary">{item.message ?? item.code ?? "Readiness item"}</span>{item.actionHint ? <p>{item.actionHint}</p> : null}</li>)}</ul></div>; }
