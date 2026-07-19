/* ── Incidents ─────────────────────────────────────────────────── */

import { request, buildQuery } from "./core";
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
  UtcTimestamp,
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
  created_at_utc?: UtcTimestamp | null;
  last_activity_at_utc?: UtcTimestamp | null;
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
  due_at_utc?: UtcTimestamp | null;
  assigned_to_user_id?: string | null;
  created_at_utc?: UtcTimestamp | null;
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
  due_at_utc?: UtcTimestamp | null;
  assigned_to_user_id?: string | null;
  created_at_utc?: UtcTimestamp | null;
}

export interface CaseWorkspaceNoteItem {
  note_id: string;
  body: string;
  note_type: NoteType;
  tags: string[];
  created_by_user_id?: string | null;
  created_at_utc: UtcTimestamp;
  edited_at_utc?: UtcTimestamp | null;
}

export interface CaseWorkspaceActivityItem {
  source: ActivitySource;
  type: string;
  occurred_at_utc: UtcTimestamp;
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
  due_at_utc?: UtcTimestamp | null;
  assigned_to_user_id?: string | null;
  assigned_at_utc?: UtcTimestamp | null;
  assigned_by_user_id?: string | null;
  created_by_user_id?: string | null;
  created_at_utc?: UtcTimestamp | null;
  completed_at_utc?: UtcTimestamp | null;
  canceled_at_utc?: UtcTimestamp | null;
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
  created_at_utc: UtcTimestamp;
  edited: boolean;
  edited_by_user_id?: string | null;
  edited_at_utc?: UtcTimestamp | null;
  updated_at_utc: UtcTimestamp;
  is_deleted: boolean;
  deleted_by_user_id?: string | null;
  deleted_at_utc?: UtcTimestamp | null;
}

export interface IncidentNotesResponse {
  items: IncidentNoteItem[];
}

export function listIncidents() {
  return request<Incident[]>("/incidents/");
}

export interface EvidenceInventoryItem {
  artifact_id: string;
  artifact_type: string;
  status: "pending" | "captured" | "unavailable";
  incident_id: string;
  case_reference: string;
  occurred_at_utc?: string | null;
  source: string;
  detail?: string | null;
  available: boolean;
}

export interface EvidenceInventoryResponse {
  items: EvidenceInventoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export function listEvidence(
  params: {
    page?: number;
    page_size?: number;
    status?: string;
    artifact_type?: string;
    search?: string;
  } = {},
) {
  return request<EvidenceInventoryResponse>(`/incidents/evidence${buildQuery(params)}`);
}

export interface CreateIncidentRequest {
  severity: IncidentSeverity;
  adc_vehicle_id: string;
  samsara_vehicle_id: string;
  adc_driver_id: string;
  window_start?: string;
  window_end?: string;
}

export interface CreateIncidentResponse {
  incident_id: string;
  status: IncidentStatus;
}

export function createIncident(data: CreateIncidentRequest) {
  return request<CreateIncidentResponse>("/incidents/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getIncident(id: string) {
  return request<IncidentDetail>(`/incidents/${id}`);
}

export interface GetIncidentQueueParams {
  status?: string;
  readiness_state?: string;
  blockers?: string;
  search?: string;
  sort?: CaseOpsQueueSort;
  page?: number;
  page_size?: number;
}

export function getIncidentQueue(params?: GetIncidentQueueParams) {
  return request<CaseOpsQueueResponse>(`/incidents/queue${buildQuery(params)}`);
}

export function getIncidentSummaryMetrics() {
  return request<CaseOpsSummaryMetrics>("/incidents/summary-metrics");
}

export function getIncidentAlerts() {
  return request<CaseOpsAlerts>("/incidents/alerts");
}

export function getMyOpenTasks(params?: { limit?: number }) {
  return request<CaseTaskWidgetResponse>(`/tasks/my-open${buildQuery(params)}`);
}

export function getOverdueTasks(params?: { limit?: number }) {
  return request<CaseTaskWidgetResponse>(`/tasks/overdue${buildQuery(params)}`);
}

export interface PatchIncidentOwnerRequest {
  operation: OwnerOperation;
  owner_user_id?: string | null;
}

export interface PatchIncidentOwnerResponse {
  incident_id: string;
  owner_user_id?: string | null;
}

export function patchIncidentOwner(incidentId: string, data: PatchIncidentOwnerRequest) {
  return request<PatchIncidentOwnerResponse>(`/incidents/${incidentId}/owner`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export interface PatchIncidentStatusRequest {
  case_status: CaseStatus;
  reason: string;
}

export interface PatchIncidentStatusResponse {
  incident_id: string;
  case_status: CaseStatus;
}

export function patchIncidentStatus(incidentId: string, data: PatchIncidentStatusRequest) {
  return request<PatchIncidentStatusResponse>(`/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function getIncidentWorkspace(incidentId: string) {
  return request<CaseWorkspaceResponse>(`/incidents/${incidentId}/workspace`);
}

export function listIncidentNotes(incidentId: string, params?: { includeDeleted?: boolean }) {
  return request<IncidentNotesResponse>(
    `/incidents/${incidentId}/notes${buildQuery({ include_deleted: params?.includeDeleted ? true : undefined })}`
  );
}

export interface CreateIncidentNoteRequest {
  body: string;
  note_type?: NoteType;
  tags?: string[];
}

export function createIncidentNote(incidentId: string, data: CreateIncidentNoteRequest) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface PatchIncidentNoteRequest {
  note_id: string;
  body?: string;
  note_type?: NoteType;
  tags?: string[];
}

export function patchIncidentNote(incidentId: string, data: PatchIncidentNoteRequest) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export interface DeleteIncidentNoteRequest {
  note_id: string;
}

export function deleteIncidentNote(incidentId: string, data: DeleteIncidentNoteRequest) {
  return request<IncidentNoteItem>(`/incidents/${incidentId}/notes`, {
    method: "DELETE",
    body: JSON.stringify(data),
  });
}

export function listIncidentTasks(incidentId: string) {
  return request<IncidentTaskListResponse>(`/incidents/${incidentId}/tasks`);
}

export interface CreateIncidentTaskRequest {
  title: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  due_at_utc?: UtcTimestamp;
  assigned_to_user_id?: string;
}

export function createIncidentTask(incidentId: string, data: CreateIncidentTaskRequest) {
  return request<IncidentTaskItem>(`/incidents/${incidentId}/tasks`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface PatchTaskRequest {
  title?: string;
  description?: string;
  task_type?: TaskType;
  priority?: TaskPriority;
  due_at_utc?: UtcTimestamp;
  assigned_to_user_id?: string;
  status?: TaskStatus;
}

export function patchTask(taskId: string, data: PatchTaskRequest) {
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

export interface CancelTaskRequest {
  reason?: string;
}

export function cancelTask(taskId: string, data?: CancelTaskRequest) {
  return request<IncidentTaskItem>(`/tasks/${taskId}/cancel`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
}
