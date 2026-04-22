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

type PendingTimelineEvent = {
  eventName: DriverTimelineEventName;
  occurredAtUtc: string;
  payload: Record<string, unknown>;
};

const pendingTimelineEvents: PendingTimelineEvent[] = [];
const MAX_PENDING_TIMELINE_EVENTS = 50;
const RETRY_FLUSH_DELAY_MS = 1500;
let timelineFlushInProgress = false;
let timelineFlushRetryTimer: ReturnType<typeof setTimeout> | null = null;

function isPersistedTimelineEventName(
  eventName: DriverProtocolEventName,
): eventName is DriverTimelineEventName {
  return PERSISTED_TIMELINE_EVENT_NAMES.has(eventName as DriverTimelineEventName);
}

function schedulePendingTimelineFlush(): void {
  if (timelineFlushRetryTimer || pendingTimelineEvents.length === 0) {
    return;
  }
  timelineFlushRetryTimer = setTimeout(() => {
    timelineFlushRetryTimer = null;
    void flushPendingTimelineEvents();
  }, RETRY_FLUSH_DELAY_MS);
}

function enqueuePendingTimelineEvent(event: PendingTimelineEvent): void {
  if (pendingTimelineEvents.length >= MAX_PENDING_TIMELINE_EVENTS) {
    pendingTimelineEvents.shift();
  }
  pendingTimelineEvents.push(event);
  schedulePendingTimelineFlush();
}

async function flushPendingTimelineEvents(): Promise<void> {
  if (timelineFlushInProgress || pendingTimelineEvents.length === 0) {
    return;
  }

  timelineFlushInProgress = true;
  try {
    const resolvedIncidentId = (await getDriverActiveIncident())?.incident_id?.trim();
    if (!resolvedIncidentId) {
      schedulePendingTimelineFlush();
      return;
    }

    const queuedEvents = pendingTimelineEvents.splice(0, pendingTimelineEvents.length);
    const failedEvents: PendingTimelineEvent[] = [];

    for (const queuedEvent of queuedEvents) {
      try {
        await postDriverTimelineEvent(resolvedIncidentId, {
          event_name: queuedEvent.eventName,
          occurred_at_utc: queuedEvent.occurredAtUtc,
          payload: queuedEvent.payload,
        });
      } catch {
        failedEvents.push(queuedEvent);
      }
    }

    if (failedEvents.length > 0) {
      pendingTimelineEvents.unshift(...failedEvents);
      schedulePendingTimelineFlush();
    }
  } finally {
    timelineFlushInProgress = false;
  }
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
      const occurredAtUtc = new Date().toISOString();
      const resolvedIncidentId =
        explicitIncidentId || (await getDriverActiveIncident())?.incident_id?.trim();
      if (!resolvedIncidentId) {
        enqueuePendingTimelineEvent({
          eventName,
          occurredAtUtc,
          payload: options?.payload ?? {},
        });
        return;
      }

      await postDriverTimelineEvent(resolvedIncidentId, {
        event_name: eventName,
        occurred_at_utc: occurredAtUtc,
        payload: options?.payload ?? {},
      });

      void flushPendingTimelineEvents();
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
