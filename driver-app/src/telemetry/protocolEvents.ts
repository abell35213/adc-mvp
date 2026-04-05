export type DriverProtocolEventName =
  | 'driver_protocol_launch_confirmed'
  | 'driver_safety_gate_viewed'
  | 'driver_safety_gate_acknowledged'
  | 'driver_emergency_call_tapped'
  | 'driver_safety_call_tapped';

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
): void {
  console.info('[driver-protocol-event]', eventName);
}
