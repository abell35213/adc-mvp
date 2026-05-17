/* ── Shared Types ───────────────────────────────────────────────── */

/* ── JSON primitives ────────────────────────────────────────────── */

/**
 * Any JSON-serializable value returned from or sent to the API.  Use
 * this instead of bare `unknown` when the value is known to be a JSON
 * document but its exact shape is not modeled (yet).
 */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/** A JSON object with string keys and {@link JsonValue} values. */
export type JsonObject = { [key: string]: JsonValue };

/**
 * ISO-8601 UTC timestamp string (e.g. `"2025-04-25T23:23:21Z"`).
 * Documentation-only alias; not branded so existing string operations
 * continue to work.
 */
export type UtcTimestamp = string;

/* ── Canonical string-union enums (mirror backend Literals) ─────── */

/**
 * Workflow status of an {@link Incident} (backend
 * `app.api.schemas.IncidentStatus`).
 */
export type IncidentStatus = "open" | "evidence_capturing" | "closed";

/**
 * Severity of an {@link Incident} (backend
 * `app.api.schemas.IncidentSeverity`).
 */
export type IncidentSeverity = "minor" | "serious" | "critical";

/**
 * Case-management status of an incident (backend
 * `app.api.schemas.IncidentCaseStatus`).
 */
export type CaseStatus =
  | "new"
  | "in_review"
  | "awaiting_evidence"
  | "awaiting_follow_up"
  | "ready_for_export"
  | "exported"
  | "escalated"
  | "closed";

/**
 * Readiness state for an incident.  The backend currently models this
 * as a free-form string with default `"not_ready"`, so this alias is
 * documentation-only and intentionally widens to `string`.
 */
export type ReadinessState = string;

/** Status of an incident task (backend `app.api.schemas.TaskStatus`). */
export type TaskStatus = "open" | "completed" | "cancelled";

/** Type of an incident task (backend `app.api.schemas.TaskType`). */
export type TaskType = "review" | "evidence" | "follow_up" | "export" | "other";

/** Priority of an incident task (backend `app.api.schemas.TaskPriority`). */
export type TaskPriority = "low" | "medium" | "high" | "urgent";

/** Type of an incident note. */
export type NoteType = "standard" | "tagged" | "decision";

/** Severity used by onboarding blockers and alert conditions. */
export type BlockerSeverity = "critical" | "warning" | "info" | "error";

/** Owner mutation operations supported by `PATCH /incidents/{id}/owner`. */
export type OwnerOperation = "assign" | "reassign" | "clear";

/**
 * Source of a driver-protocol instruction set (backend
 * `app.api.schemas.InstructionScope`).
 */
export type InstructionSource = "default" | "company" | "insurer";

/** Source of a workspace activity item. */
export type ActivitySource = "event" | "audit";

/**
 * Status of an integration connection (backend
 * `app.api.schemas.IntegrationConnectionStatus`).
 */
export type IntegrationConnectionStatus =
  | "pending"
  | "active"
  | "inactive"
  | "error";

/** Aggregated health status reported on the ops dashboard. */
export type IntegrationHealthStatus = "healthy" | "degraded";

/**
 * Status of an onboarding-side import job.  Distinct from
 * {@link ImportJobStatus} because the onboarding response uses
 * `"queued"` instead of `"pending"` for the initial state.
 */
export type OnboardingImportJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

/* ── Domain types ───────────────────────────────────────────────── */

export type ExportType =
  | "court_defense"
  | "insurer_packet"
  | "internal_review"
  | "compliance_audit";

export type ExportStatus =
  | "requested"
  | "queued"
  | "processing"
  | "ready"
  | "failed"
  | "expired";

export type ExportProgressStage =
  | "request_accepted"
  | "gathering_incident_data"
  | "assembling_documents"
  | "packaging_evidence"
  | "uploading_export"
  | "ready_for_download";

export interface DriverResponseSummary {
  notification_sent_at_utc?: UtcTimestamp | null;
  acknowledged_at_utc?: UtcTimestamp | null;
  uploads_complete?: boolean;
  uploads_completed_at_utc?: UtcTimestamp | null;
  awaiting_driver_action?: boolean;
}

export interface DriverProtocolSummary {
  instruction_source?: string;
  require_ack?: boolean;
  sms_enabled?: boolean;
  voice_enabled?: boolean;
  safety_manager_phone?: string | null;
}

export interface ArtifactSummary {
  artifact_id: string;
  artifact_type: string;
  status: string;
  captured_at_utc?: UtcTimestamp | null;
  unavailable_reason?: string | null;
}

export interface ExportSummary {
  export_id: string;
  incident_id?: string | null;
  export_type: ExportType;
  profile_id: string;
  requested_by_user_id?: string | null;
  retry_parent_export_id?: string | null;
  options_json: JsonObject;
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  error_message?: string | null;
  package_sha256?: string | null;
  byte_size?: number | null;
  artifact_count: number;
  timeline_event_count: number;
  requested_at_utc?: UtcTimestamp | null;
  processing_started_at_utc?: UtcTimestamp | null;
  completed_at_utc?: UtcTimestamp | null;
  expires_at_utc?: UtcTimestamp | null;
  created_at_utc?: UtcTimestamp | null;
  updated_at_utc?: UtcTimestamp | null;
  generated_by?: string | null;
  generation_duration_seconds?: number | null;
  failure_count?: number | null;
  failure_reason?: string | null;
  retry_guidance?: string | null;
  readiness?: {
    required_artifacts_present?: boolean | null;
    custody_complete?: boolean | null;
    integrity_checks_passed?: boolean | null;
  } | null;
}

/**
 * A summary of an export along with its originating incident.  When
 * listing all exports across an organization, the backend returns the
 * associated incident_id so that the UI can link back to the incident
 * detail page.  This structure extends the base ExportSummary.
 */
export interface ExportListItem extends ExportSummary {
  /**
   * Identifier of the incident this export belongs to.  Useful for
   * navigating back to the source incident after downloading a package.
   */
  incident_id: string;
}

export interface EventSummary {
  event_type: string;
  occurred_at_utc: UtcTimestamp;
  actor_type: string;
  payload?: JsonObject | null;
}

export interface Incident {
  incident_id: string;
  status: IncidentStatus;
  severity: IncidentSeverity | null;
  adc_vehicle_id: string | null;
  samsara_vehicle_id: string | null;
  adc_driver_id: string | null;
  created_at_utc?: UtcTimestamp;
  evidence_captured?: number;
  evidence_total?: number;
  completeness_percent?: number;
  completeness_status?: string;
  readiness_state?: ReadinessState;
  blocker_counts?: Record<string, number>;
  driver_response?: DriverResponseSummary | null;
  driver_protocol_summary?: DriverProtocolSummary | null;
}

/**
 * Single entry in {@link IncidentDetail.blockers}.  Mirrors the inline
 * shape returned by the backend; promoted to a named interface so it
 * can be shared with consumer components.
 */
export interface IncidentBlocker {
  code: string;
  message: string;
  severity: BlockerSeverity;
}



export interface CurrentWeatherConditions {
  capture_status?: string | null;
  normalized_weather?: JsonObject;
  raw_source_metadata?: JsonObject;
}

export interface WeatherSnapshotArtifactReference {
  artifact_id: string;
  artifact_type: string;
  status: string;
}

export interface IncidentDetail extends Incident {
  evidence_inventory: ArtifactSummary[];
  export_status: ExportSummary[];
  timeline: EventSummary[];
  completeness_missing_items?: string[];
  blockers?: IncidentBlocker[];
  current_weather_conditions?: CurrentWeatherConditions | null;
  weather_snapshot_status?: string | null;
  weather_location_source?: string | null;
  weather_satellite_snapshot_artifact?: WeatherSnapshotArtifactReference | null;
}

export type OnboardingStepStatus =
  | "not_started"
  | "in_progress"
  | "completed"
  | "blocked";

export type OnboardingReadinessStatus =
  | "not_started"
  | "in_progress"
  | "blocked"
  | "pilot_ready"
  | "launch_ready";

export type ImportJobStatus = "pending" | "running" | "succeeded" | "failed";

export type CaseOpsQueueSort = "urgency" | "readiness" | "newest";
