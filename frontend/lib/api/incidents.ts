/* ── Incidents ─────────────────────────────────────────────────── */

import { request } from "./core";
import type {
  Incident,
  IncidentDetail,
  CaseOpsQueueSort,
  CaseStatus,
  IncidentSeverity,
  IncidentStatus,
  ReadinessState,
  TaskStatus,
  TaskPriority,
  TaskType,
  NoteType,
  ActivitySource,
  OwnerOperation,
  JsonObject,
} from "./types";

export interface CaseOpsQueueBlockerCounts {
  total: number;
  critical: number;
  important: number;
  optional: number;
}

export interface CaseOpsQueueItem {
  incident_id: string;
  case_status: CaseStatus;
  owner_user_id?: string | null;
  readiness_state: ReadinessState;
  created_at_utc?: string | null;
  last_activity_at_utc?: string | null;
  severity?: IncidentSeverity | null;
  adc_vehicle_id?: string | null;
  adc_driver_id?: string | null;
  completeness_percent: number;
  blockers: CaseOpsQueueBlockerCounts;
}

export interface CaseOpsQueueResponse {
  items: CaseOpsQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CaseOpsSummaryMetrics {
  open_incidents: number;
  unassigned_incidents: number;
  blocked_incidents: number;
  export_aging_incidents: number;
  stalled_incidents: number;
  overdue_tasks: number;
}

export interface CaseOpsAlerts {
  stalled: number;
  unassigned: number;
  overdue: number;
  blocked: number;
  export_aging: number;
}

export interface CaseTaskWidgetItem {
  task_id: string;
  incident_id: string;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_at_utc?: string | null;
  assigned_to_user_id?: string | null;
  created_at_utc?: string | null;
}

export interface CaseTaskWidgetResponse {
  items: CaseTaskWidgetItem[];
}

export interface CaseWorkspaceOwner {
  user_id: string;
  email?: string | null;
}

export interface CaseWorkspaceCompletenessSection {
  name: string;
  earned: number;
  possible: number;
  percent: number;
  status: string;
  missing_items: string[];
}

export interface CaseWorkspaceCompleteness {
  percent: number;
  status: string;
  missing_items: string[];
  sections: CaseWorkspaceCompletenessSection[];
}

export interface CaseWorkspaceEvidenceSummary {
  total: number;
  captured: number;
  pending: number;
  unavailable: number;
}

export interface CaseWorkspaceTaskItem {
  task_id: string;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_at_utc?: string | null;
  assigned_to_user_id?: string | null;
  created_at_utc?: string | null;
}

export interface CaseWorkspaceNoteItem {
  note_id: string;
  body: string;
  note_type: NoteType;
  tags: string[];
  created_by_user_id?: string | null;
  created_at_utc: string;
  edited_at_utc?: string | null;
}

export interface CaseWorkspaceActivityItem {
  source: ActivitySource;
  type: string;
  occurred_at_utc: string;
  actor_type: string;
  actor_id: string;
  detail: JsonObject;
}

export interface CaseWorkspaceResponse {
  incident_id: string;
  owner?: CaseWorkspaceOwner | null;
  case_status: CaseStatus;
  readiness_state: ReadinessState;
  completeness: CaseWorkspaceCompleteness;
  blockers: JsonObject[];
  evidence_summary: CaseWorkspaceEvidenceSummary;
  missing_items: string[];
  open_tasks: CaseWorkspaceTaskItem[];
  recent_notes: CaseWorkspaceNoteItem[];
  activity: CaseWorkspaceActivityItem[];
}

export interface IncidentTaskItem {
  task_id: string;
  incident_id: string;
  title: string;
  description?: string | null;
  task_type: TaskType;
  status: TaskStatus;
  priority: TaskPriority;
  due_at_utc?: string | null;
  assigned_to_user_id?: string | null;
  assigned_at_utc?: string | null;
  assigned_by_user_id?: string | null;
  created_by_user_id?: string | null;
  created_at_utc?: string | null;
  completed_at_utc?: string | null;
  canceled_at_utc?: string | null;
  canceled_reason?: string | null;
  overdue: boolean;
}

export interface IncidentTaskListResponse {
  items: IncidentTaskItem[];
}

export interface IncidentNoteItem {
  note_id: string;
  incident_id: string;
  body: string;
  note_type: NoteType;
  tags: string[];
  created_by_user_id?: string | null;
  created_at_utc: string;
  edited: boolean;
  edited_by_user_id?: string | null;
  edited_at_utc?: string | null;
  updated_at_utc: string;
  is_deleted: boolean;
  deleted_by_user_id?: string | null;
  deleted_at_utc?: string | null;
}

export interface IncidentNotesResponse {
  items: IncidentNoteItem[];
}

export function listIncidents() {
  return request<Incident[]>("/incidents/");
}

export function createIncident(data: {
  severity: IncidentSeverity;
  adc_vehicle_id: string;
  samsara_vehicle_id: string;
  adc_driver_id: string;
  window_start?: string;
  window_end?: string;
}) {
  return request<{ incident_id: string; status: IncidentStatus }>("/incidents/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getIncident(id: string) {
  return request<IncidentDetail>(`/incidents/${id}`);
}

export function getIncidentQueue(params?: {
  status?: string;
  readiness_state?: string;
  blockers?: string;
  search?: string;
  sort?: CaseOpsQueueSort;
  page?: number;
  page_size?: number;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.readiness_state) query.set("readiness_state", params.readiness_state);
  if (params?.blockers) query.set("blockers", params.blockers);
  if (params?.search) query.set("search", params.search);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<CaseOpsQueueResponse>(`/incidents/queue${suffix}`);
}

export function getIncidentSummaryMetrics() {
  return request<CaseOpsSummaryMetrics>("/incidents/summary-metrics");
}

export function getIncidentAlerts() {
  return request<CaseOpsAlerts>("/incidents/alerts");
}

export function getMyOpenTasks(params?: { limit?: number }) {
  const suffix = params?.limit ? `?limit=${params.limit}` : "";
  return request<CaseTaskWidgetResponse>(`/tasks/my-open${suffix}`);
}

export function getOverdueTasks(params?: { limit?: number }) {
  const suffix = params?.limit ? `?limit=${params.limit}` : "";
  return request<CaseTaskWidgetResponse>(`/tasks/overdue${suffix}`);
}

export function patchIncidentOwner(incidentId: string, data: {
  operation: OwnerOperation;
  owner_user_id?: string | null;
}) {
  return request<{ incident_id: string; owner_user_id?: string | null }>(`/incidents/${incidentId}/owner`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function patchIncidentStatus(incidentId: string, data: {
  case_status: CaseStatus;
  reason: string;
}) {
  return request<{ incident_id: string; case_status: CaseStatus }>(`/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function getIncidentWorkspace(incidentId: string) {
  return request<CaseWorkspaceResponse>(`/incidents/${incidentId}/workspace`);
}

export function listIncidentNotes(incidentId: string, params?: { includeDeleted?: boolean }) {
  const suffix = params?.includeDeleted ? "?include_deleted=true" : "";
  return request<IncidentNotesResponse>(`/incidents/${incidentId}/notes${suffix}`);
}

export function createIncidentNote(incidentId: string, data: {
  body: string;
  note_type?: NoteType;
  tags?: string[];
}) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function patchIncidentNote(incidentId: string, data: {
  note_id: string;
  body?: string;
  note_type?: NoteType;
  tags?: string[];
}) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteIncidentNote(incidentId: string, data: { note_id: string }) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "DELETE",
    body: JSON.stringify(data),
  });
}

export function listIncidentTasks(incidentId: string) {
  return request<IncidentTaskListResponse>(`/incidents/${incidentId}/tasks`);
}

export function createIncidentTask(incidentId: string, data: {
  title: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  due_at_utc?: string;
  assigned_to_user_id?: string;
}) {
  return request<IncidentTaskItem>(`/incidents/${incidentId}/tasks`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function patchTask(taskId: string, data: {
  title?: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  due_at_utc?: string;
  assigned_to_user_id?: string;
  status?: TaskStatus;
}) {
  return request<IncidentTaskItem>(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function completeTask(taskId: string) {
  return request<IncidentTaskItem>(`/tasks/${taskId}/complete`, {
    method: "POST",
  });
}

export function cancelTask(taskId: string, data?: { reason?: string }) {
  return request<IncidentTaskItem>(`/tasks/${taskId}/cancel`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
}
