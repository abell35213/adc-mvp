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
  | 'driver_report_submitted';

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
): void {
  console.info('[driver-protocol-event]', eventName);
}
