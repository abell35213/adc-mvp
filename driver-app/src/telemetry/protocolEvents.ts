import {
  DriverTimelineEventName,
  getDriverActiveIncident,
  postDriverTimelineEvent,
} from '../api';

export type DriverProtocolEventName =
  | 'driver_protocol_launch_confirmed'
  | 'driver_safety_gate_viewed'
  | 'driver_safety_gate_acknowledged'
  | 'driver_emergency_call_tapped'
  | 'driver_safety_call_tapped'
  | 'driver_instruction_step_viewed'
  | 'driver_instruction_step_acknowledged'
  | 'driver_scene_facts_saved'
  | 'driver_parties_saved'
  | 'driver_narrative_saved'
  | 'driver_report_submitted'
  | 'driver_media_uploaded'
  | 'driver_media_upload_failed';

export type DriverUploadAnalyticsEventName =
  | 'driver_upload_attempted'
  | 'driver_upload_retry_scheduled'
  | 'driver_upload_succeeded'
  | 'driver_upload_failed';

export type ProtocolAnalyticsEventName =
  | 'protocol_start_tapped'
  | 'vehicle_confirmed'
  | 'qr_scan_started'
  | 'qr_scan_success'
  | 'qr_scan_failed'
  | 'safety_gate_acknowledged'
  | 'incident_initiated'
  | 'instruction_acknowledged'
  | 'scene_saved'
  | 'party_info_saved'
  | 'artifact_capture_started'
  | 'artifact_upload_success'
  | 'artifact_upload_failed'
  | 'narrative_saved'
  | 'driver_report_submitted'
  | 'protocol_resumed';

const PERSISTED_TIMELINE_EVENT_NAMES: Set<DriverTimelineEventName> = new Set([
  'driver_protocol_launch_confirmed',
  'driver_safety_gate_viewed',
  'driver_safety_gate_acknowledged',
  'driver_instruction_step_viewed',
  'driver_instruction_step_acknowledged',
  'driver_scene_facts_saved',
  'driver_parties_saved',
  'driver_media_uploaded',
  'driver_media_upload_failed',
  'driver_narrative_saved',
  'driver_report_submitted',
]);

function isPersistedTimelineEventName(
  eventName: DriverProtocolEventName,
): eventName is DriverTimelineEventName {
  return PERSISTED_TIMELINE_EVENT_NAMES.has(eventName as DriverTimelineEventName);
}

async function resolveIncidentCorrelationId(explicitIncidentId?: string | null) {
  const trimmedIncidentId = explicitIncidentId?.trim();
  return trimmedIncidentId || (await getDriverActiveIncident())?.incident_id?.trim() || null;
}

function createCorrelatedPayload(
  payload: Record<string, unknown> | undefined,
  correlations: {
    incidentCorrelationId: string | null;
    workflowCorrelationId?: string | null;
  },
): Record<string, unknown> {
  return {
    ...(payload ?? {}),
    incident_correlation_id: correlations.incidentCorrelationId,
    workflow_correlation_id: correlations.workflowCorrelationId ?? null,
  };
}

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
  options?: {
    incidentId?: string | null;
    workflowCorrelationId?: string | null;
    payload?: Record<string, unknown>;
  },
): void {
  // Event names alone are non-PII, but only log them in dev builds to keep
  // production logs (which may be aggregated by a third-party crash reporter)
  // free of any signal that could leak driver activity.
  if (typeof __DEV__ !== 'undefined' && __DEV__) {
    // eslint-disable-next-line no-console
    console.info('[driver-protocol-event]', eventName);
  }
  void (async () => {
    try {
      const resolvedIncidentId = await resolveIncidentCorrelationId(options?.incidentId);
      const correlatedPayload = createCorrelatedPayload(options?.payload, {
        incidentCorrelationId: resolvedIncidentId,
        workflowCorrelationId: options?.workflowCorrelationId,
      });

      if (!isPersistedTimelineEventName(eventName) || !resolvedIncidentId) {
        return;
      }

      await postDriverTimelineEvent(resolvedIncidentId, {
        event_name: eventName,
        occurred_at_utc: new Date().toISOString(),
        payload: correlatedPayload,
      });
    } catch {
      // Non-blocking telemetry write.
    }
  })().catch(() => {
    // Defense-in-depth: the inner try/catch should always handle errors, but if
    // the runtime ever rejects the IIFE itself we don't want an unhandled
    // promise rejection to crash the JS engine in release builds.
  });
}

export function emitUploadAnalyticsEvent(
  eventName: DriverUploadAnalyticsEventName,
  payload: Record<string, unknown>,
): void {
  // ``payload`` may include incident IDs and other identifiers — do not log
  // outside of dev builds.
  if (typeof __DEV__ !== 'undefined' && __DEV__) {
    // eslint-disable-next-line no-console
    console.info('[driver-upload-analytics-event]', eventName, payload);
  }
}

export function emitProtocolAnalyticsEvent(
  eventName: ProtocolAnalyticsEventName,
  options?: {
    incidentId?: string | null;
    workflowCorrelationId?: string | null;
    payload?: Record<string, unknown>;
  },
): void {
  void (async () => {
    try {
      const resolvedIncidentId = await resolveIncidentCorrelationId(options?.incidentId);
      const correlatedPayload = createCorrelatedPayload(options?.payload, {
        incidentCorrelationId: resolvedIncidentId,
        workflowCorrelationId: options?.workflowCorrelationId,
      });
      if (typeof __DEV__ !== 'undefined' && __DEV__) {
        // eslint-disable-next-line no-console
        console.info('[driver-protocol-analytics-event]', eventName, correlatedPayload);
      }
    } catch {
      // Non-blocking analytics emission.
    }
  })().catch(() => {
    // See emitTimelineAndAnalyticsEvent — defense-in-depth against unhandled rejections.
  });
}
