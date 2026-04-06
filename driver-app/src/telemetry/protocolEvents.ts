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

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
  options?: {
    incidentId?: string | null;
    payload?: Record<string, unknown>;
  },
): void {
  console.info('[driver-protocol-event]', eventName);
  if (!isPersistedTimelineEventName(eventName)) {
    return;
  }

  void (async () => {
    try {
      const explicitIncidentId = options?.incidentId?.trim();
      const resolvedIncidentId =
        explicitIncidentId || (await getDriverActiveIncident())?.incident_id?.trim();
      if (!resolvedIncidentId) {
        return;
      }

      await postDriverTimelineEvent(resolvedIncidentId, {
        event_name: eventName,
        occurred_at_utc: new Date().toISOString(),
        payload: options?.payload ?? {},
      });
    } catch {
      // Non-blocking telemetry write.
    }
  })();
}

export function emitUploadAnalyticsEvent(
  eventName: DriverUploadAnalyticsEventName,
  payload: Record<string, unknown>,
): void {
  console.info('[driver-upload-analytics-event]', eventName, payload);
}
