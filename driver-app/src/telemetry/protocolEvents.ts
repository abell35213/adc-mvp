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

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
): void {
  console.info('[driver-protocol-event]', eventName);
}

export function emitUploadAnalyticsEvent(
  eventName: DriverUploadAnalyticsEventName,
  payload: Record<string, unknown>,
): void {
  console.info('[driver-upload-analytics-event]', eventName, payload);
}
