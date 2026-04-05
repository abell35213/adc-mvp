export type DriverProtocolEventName = 'driver_protocol_launch_confirmed';

export function emitTimelineAndAnalyticsEvent(
  eventName: DriverProtocolEventName,
): void {
  console.info('[driver-protocol-event]', eventName);
}
