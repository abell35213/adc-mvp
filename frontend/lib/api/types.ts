/* ── Shared Types ───────────────────────────────────────────────── */

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
  notification_sent_at_utc?: string | null;
  acknowledged_at_utc?: string | null;
  uploads_complete?: boolean;
  uploads_completed_at_utc?: string | null;
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
  captured_at_utc?: string | null;
  unavailable_reason?: string | null;
}

export interface ExportSummary {
  export_id: string;
  incident_id?: string | null;
  export_type: ExportType;
  profile_id: string;
  requested_by_user_id?: string | null;
  retry_parent_export_id?: string | null;
  options_json: Record<string, unknown>;
  status: ExportStatus;
  progress_stage: ExportProgressStage;
  error_message?: string | null;
  package_sha256?: string | null;
  byte_size?: number | null;
  artifact_count: number;
  timeline_event_count: number;
  requested_at_utc?: string | null;
  processing_started_at_utc?: string | null;
  completed_at_utc?: string | null;
  expires_at_utc?: string | null;
  created_at_utc?: string | null;
  updated_at_utc?: string | null;
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
  occurred_at_utc: string;
  actor_type: string;
  payload?: Record<string, unknown> | null;
}

export interface Incident {
  incident_id: string;
  status: string;
  severity: string | null;
  adc_vehicle_id: string | null;
  samsara_vehicle_id: string | null;
  adc_driver_id: string | null;
  created_at_utc?: string;
  evidence_captured?: number;
  evidence_total?: number;
  completeness_percent?: number;
  completeness_status?: string;
  readiness_state?: string;
  blocker_counts?: Record<string, number>;
  driver_response?: DriverResponseSummary | null;
  driver_protocol_summary?: DriverProtocolSummary | null;
}

export interface IncidentDetail extends Incident {
  evidence_inventory: ArtifactSummary[];
  export_status: ExportSummary[];
  timeline: EventSummary[];
  completeness_missing_items?: string[];
  blockers?: Array<{ code: string; message: string; severity: string }>;
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
