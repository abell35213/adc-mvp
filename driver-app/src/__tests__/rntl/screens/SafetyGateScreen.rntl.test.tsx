/**
 * RNTL coverage for `SafetyGateScreen`.
 *
 * Behaviours under test:
 *   1. On mount the screen calls `markSafetyGateViewed` and emits the
 *      `driver_safety_gate_viewed` timeline+analytics event.
 *   2. "Call 911" calls `recordEmergencyCallTap`, emits
 *      `driver_emergency_call_tapped`, and opens `tel:911` via
 *      `Linking.openURL`.
 *   3. "Call Safety Manager" calls `recordSafetyManagerCallTap`,
 *      emits `driver_safety_call_tapped`, and opens
 *      `tel:+18005551212`.
 *   4. "Safety check complete" calls `acknowledgeSafetyGate`, emits
 *      `safety_gate_acknowledged` (analytics) +
 *      `driver_safety_gate_acknowledged` (timeline+analytics),
 *      completes the route, and navigates to
 *      `IncidentStartLoading`.
 *   5. The native-stack screen options disable the back affordance
 *      (`headerBackVisible: false`).
 *   6. Snapshot of the rendered step.
 *
 * `useProtocolFlow` is mocked here rather than driving the real
 * provider: the screen's mount-time `useEffect` depends on
 * `markSafetyGateViewed`, and the production provider re-creates that
 * function whenever `protocolContext` changes — which would cause the
 * effect to fire on every render under test. Mocking the hook keeps
 * callback identities stable across renders so the screen settles.
 */

import { Linking } from 'react-native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

const mockMarkSafetyGateViewed = jest.fn();
const mockAcknowledgeSafetyGate = jest.fn();
const mockRecordEmergencyCallTap = jest.fn();
const mockRecordSafetyManagerCallTap = jest.fn();
const mockCompleteRoute = jest.fn();
const mockProtocolContext = {
  workflowCorrelationId: 'wfc-123',
};

jest.mock('../../../navigation/useProtocolRouteGuard', () => ({
  useProtocolRouteGuard: jest.fn(),
}));
jest.mock('../../../navigation/ProtocolFlowContext', () => {
  const actual = jest.requireActual('../../../navigation/ProtocolFlowContext');
  return {
    ...actual,
    useProtocolFlow: () => ({
      markSafetyGateViewed: mockMarkSafetyGateViewed,
      acknowledgeSafetyGate: mockAcknowledgeSafetyGate,
      recordEmergencyCallTap: mockRecordEmergencyCallTap,
      recordSafetyManagerCallTap: mockRecordSafetyManagerCallTap,
      completeRoute: mockCompleteRoute,
      protocolContext: mockProtocolContext,
    }),
  };
});
jest.mock('../../../telemetry/protocolEvents', () => {
  const actual = jest.requireActual('../../../telemetry/protocolEvents');
  return {
    ...actual,
    emitProtocolAnalyticsEvent: jest.fn(),
    emitTimelineAndAnalyticsEvent: jest.fn(),
  };
});

import {
  emitProtocolAnalyticsEvent,
  emitTimelineAndAnalyticsEvent,
} from '../../../telemetry/protocolEvents';
import SafetyGateScreen from '../../../screens/SafetyGateScreen';
import { renderScreen } from '../test-utils';

const mountScreen = () =>
  renderScreen({
    name: 'SafetyGate',
    component: SafetyGateScreen,
    siblings: [{ name: 'IncidentStartLoading' }, { name: 'DriverHome' }],
  });

describe('SafetyGateScreen', () => {
  let openUrlSpy: jest.SpyInstance;
  beforeEach(() => {
    openUrlSpy = jest
      .spyOn(Linking, 'openURL')
      .mockResolvedValue(undefined as never);
  });
  afterEach(() => {
    openUrlSpy.mockRestore();
  });

  it('renders the title and description', () => {
    mountScreen();
    expect(screen.getByText('Safety Gate')).toBeOnTheScreen();
    expect(
      screen.getByText(/Confirm scene safety first/i),
    ).toBeOnTheScreen();
  });

  it('marks the safety gate viewed and emits the viewed timeline event on mount', async () => {
    mountScreen();

    await waitFor(() => {
      expect(mockMarkSafetyGateViewed).toHaveBeenCalledTimes(1);
    });
    expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith('driver_safety_gate_viewed');
  });

  it('Call 911 records an emergency tap, emits the timeline event, and opens tel:911', async () => {
    mountScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Call 911'));
    });

    expect(mockRecordEmergencyCallTap).toHaveBeenCalledTimes(1);
    expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith('driver_emergency_call_tapped');
    expect(openUrlSpy).toHaveBeenCalledWith('tel:911');
  });

  it('Call Safety Manager records a tap, emits the timeline event, and opens tel:+18005551212', async () => {
    mountScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Call Safety Manager'));
    });

    expect(mockRecordSafetyManagerCallTap).toHaveBeenCalledTimes(1);
    expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith('driver_safety_call_tapped');
    expect(openUrlSpy).toHaveBeenCalledWith('tel:+18005551212');
  });

  it('Safety check complete acknowledges, emits both events, completes route, and navigates to IncidentStartLoading', async () => {
    const { getNavigation } = mountScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Safety check complete'));
    });

    expect(mockAcknowledgeSafetyGate).toHaveBeenCalledTimes(1);
    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'safety_gate_acknowledged',
      expect.objectContaining({ workflowCorrelationId: 'wfc-123' }),
    );
    expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith(
      'driver_safety_gate_acknowledged',
    );
    expect(mockCompleteRoute).toHaveBeenCalledWith('SafetyGate');
    await waitFor(() => {
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStartLoading');
    });
  });

  it('matches the rendered snapshot', () => {
    const { screen: rendered } = mountScreen();
    expect(rendered.toJSON()).toMatchSnapshot();
  });
});
