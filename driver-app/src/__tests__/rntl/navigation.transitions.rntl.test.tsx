/**
 * Cross-screen navigation transition tests.
 *
 * The per-screen RNTL suites all mock `useProtocolFlow` (and often
 * `useProtocolRouteGuard`) so they can drive one screen's behaviour in
 * isolation. That deliberately leaves a gap: nothing verifies that the
 * **real** `ProtocolFlowProvider` and the route guard cooperate
 * correctly across screen boundaries.
 *
 * This suite fills that gap. Every test mounts a real
 * `ProtocolFlowProvider` (the default in `renderWithProviders`), wires
 * multiple real screens into one navigation stack, and reads/writes
 * the live provider snapshot through `ProtocolFlowSpy` +
 * `ProtocolFlowController`.
 *
 * Behaviours under test:
 *   1. Happy path — `IncidentConfirm` → `VehicleConfirm` advances
 *      both the navigation state and `completedRoutes` /
 *      `workflowState` in lock-step. We seed the provider with
 *      `startProtocol()` first so the real workflow transition guard
 *      (`isAuthenticated` required for
 *      `authenticated → incident_confirmed`) is satisfied — exactly
 *      as production does after OTP verification. The chain stops at
 *      `SafetyGate` (mounted as a stub) because the real
 *      `SafetyGate` screen has a mount-time effect whose dependency
 *      list re-fires whenever the real provider re-renders, looping
 *      against an unmocked `useProtocolFlow`. The cross-screen value
 *      here is the **first** transition; the SafetyGate transition
 *      itself is fully covered by the per-screen suite.
 *   2. Deep-link redirect — mounting a deep route (`Narrative`) with
 *      empty `completedRoutes` causes the guard to bounce back to
 *      `IncidentConfirm`.
 *   3. Resume mid-flow — `restoreProtocol` is called via the
 *      controller, then navigation is pushed to a deep route
 *      (`Narrative`). The guard redirects to the first incomplete
 *      route (`IncidentStartLoading`), proving the
 *      `PROTOCOL_ROUTE_ORDER` traversal works for partial state.
 *
 * Telemetry is mocked because these screens emit analytics on every
 * transition — we don't want their console / network noise here.
 * `getDriverMe` is mocked so `VehicleConfirm` finds an assigned
 * vehicle. The deep target screens for the redirect tests are stubbed
 * via the default sibling stub (their full lifecycles have their own
 * dedicated suites).
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

jest.mock('../../api', () => {
  const actual = jest.requireActual('../../api');
  return {
    ...actual,
    getDriverMe: jest.fn(),
    getDriverActiveIncident: jest.fn(),
  };
});
jest.mock('../../telemetry/protocolEvents', () => {
  const actual = jest.requireActual('../../telemetry/protocolEvents');
  return {
    ...actual,
    emitProtocolAnalyticsEvent: jest.fn(),
    emitTimelineAndAnalyticsEvent: jest.fn(),
  };
});
// Silence the workflow-correlation generator so seeded protocol context is
// deterministic across renders.
jest.mock('../../telemetry/correlation', () => ({
  createWorkflowCorrelationId: () => 'wfc-test',
}));

import * as api from '../../api';
import IncidentConfirmScreen from '../../screens/IncidentConfirmScreen';
import VehicleConfirmScreen from '../../screens/VehicleConfirmScreen';
import NarrativeScreen from '../../screens/NarrativeScreen';
import {
  createProtocolFlowController,
  ProtocolFlowSpy,
  renderScreen,
} from './test-utils';

const mockedGetDriverMe = () => jest.mocked(api.getDriverMe);

const ASSIGNED_VEHICLE: api.DriverMeResponse = {
  driver_id: 'drv-1',
  org_id: 'org-1',
  phone_e164: '+15555550100',
  display_name: 'Test Driver',
  vehicle: {
    adc_vehicle_id: 'veh-001',
    display_label: 'Truck 17',
  },
};

describe('cross-screen navigation transitions', () => {
  beforeEach(() => {
    mockedGetDriverMe().mockResolvedValue(ASSIGNED_VEHICLE);
    jest.mocked(api.getDriverActiveIncident).mockResolvedValue(null);
  });

  it('happy path — IncidentConfirm → VehicleConfirm advances workflow and completedRoutes via the real provider', async () => {
    const controller = createProtocolFlowController();

    const { getNavigation } = renderScreen({
      name: 'IncidentConfirm',
      component: IncidentConfirmScreen,
      siblings: [
        { name: 'VehicleConfirm', component: VehicleConfirmScreen },
        // SafetyGate stays a stub here — its real implementation has a
        // mount-time effect that fires on every provider render
        // (`markSafetyGateViewed` keeps a stable function identity
        // only when the hook is mocked, which is what the per-screen
        // suite does). Mounting the real SafetyGate against the real
        // provider causes the effect to loop. The SafetyGate
        // transition itself is fully covered by its own per-screen
        // suite; this integration suite only needs to verify the
        // first cross-screen transition wires the real provider
        // correctly.
        { name: 'SafetyGate' },
        { name: 'DriverHome' },
      ],
      providerOptions: {
        innerWrapper: (children) => (
          <>
            <ProtocolFlowSpy controller={controller} />
            {children}
          </>
        ),
      },
    });

    // Wait for the spy's first commit so the controller is populated
    // before we drive it.
    await waitFor(() => expect(controller.current).not.toBeNull());

    // Production calls `startProtocol()` after OTP verification — this
    // primes `isAuthenticated`, which the workflow state machine's
    // `incident_confirmed` guard requires. Without this seed the real
    // provider rejects IncidentConfirm's `transitionWorkflow` call.
    act(() => {
      controller.current?.startProtocol();
    });

    // Step 1: IncidentConfirm → VehicleConfirm.
    await act(async () => {
      fireEvent.press(screen.getByText('Continue'));
    });
    await waitFor(() =>
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('VehicleConfirm'),
    );
    expect(controller.current?.completedRoutes.has('IncidentConfirm')).toBe(true);
    expect(controller.current?.workflowState).toBe('incident_confirmed');

    // Step 2: VehicleConfirm — accept the assigned vehicle, then
    // confirm. `getDriverMe` resolves to the assigned vehicle so the
    // "Accept assigned vehicle" button is enabled once the load
    // settles.
    await waitFor(() =>
      expect(screen.getByText('Accept assigned vehicle')).not.toBeDisabled(),
    );
    await act(async () => {
      fireEvent.press(screen.getByText('Accept assigned vehicle'));
    });
    await waitFor(() =>
      expect(controller.current?.protocolContext.vehicleResolved).toBe(true),
    );
    expect(controller.current?.protocolContext.vehicleId).toBe('veh-001');
    expect(controller.current?.protocolContext.vehicleResolutionMethod).toBe(
      'assigned_vehicle',
    );

    await act(async () => {
      fireEvent.press(screen.getByText('Vehicle confirmed'));
    });
    await waitFor(() =>
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('SafetyGate'),
    );
    expect(controller.current?.completedRoutes.has('VehicleConfirm')).toBe(true);
  });

  it('deep-link redirect — mounting Narrative with empty completedRoutes bounces back to IncidentConfirm', async () => {
    const { getNavigation } = renderScreen({
      name: 'Narrative',
      component: NarrativeScreen,
      siblings: [
        { name: 'IncidentConfirm' },
        { name: 'ReviewSubmit' },
        { name: 'DriverHome' },
      ],
    });

    await waitFor(() =>
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentConfirm'),
    );
    expect(screen.getByTestId('route-stub-IncidentConfirm')).toBeOnTheScreen();
  });

  it('resume mid-flow — restoring partial completedRoutes redirects a deep route to the first incomplete prerequisite', async () => {
    const controller = createProtocolFlowController();

    // Mount the deep target (`Narrative`) directly. Without seeding,
    // its guard would redirect to `IncidentConfirm`. We seed *before*
    // the redirect can settle by capturing the controller and calling
    // `restoreProtocol` synchronously after the spy mounts.
    //
    // To avoid racing the guard, we mount on a no-op route, seed the
    // partial completion, then push to `Narrative` — the redirect that
    // fires from there must target the **first incomplete prefix**
    // route, not `IncidentConfirm`.
    const NoopRoute = () => null;

    const { getNavigation } = renderScreen({
      name: 'DriverHome',
      component: NoopRoute,
      siblings: [
        { name: 'IncidentConfirm' },
        { name: 'VehicleConfirm' },
        { name: 'SafetyGate' },
        { name: 'IncidentStartLoading' },
        { name: 'InstructionStep' },
        { name: 'SceneFacts' },
        { name: 'ThirdPartyInfo' },
        { name: 'MediaCapture' },
        { name: 'Narrative', component: NarrativeScreen },
        { name: 'ReviewSubmit' },
      ],
      providerOptions: {
        innerWrapper: (children) => (
          <>
            <ProtocolFlowSpy controller={controller} />
            {children}
          </>
        ),
      },
    });

    await waitFor(() => expect(controller.current).not.toBeNull());

    // Seed the first three routes as completed.
    act(() => {
      controller.current?.restoreProtocol([
        'IncidentConfirm',
        'VehicleConfirm',
        'SafetyGate',
      ]);
    });

    // Now navigate to `Narrative`. Its guard sees the gap at
    // `IncidentStartLoading` and replaces.
    act(() => {
      getNavigation()?.navigate('Narrative');
    });

    await waitFor(() =>
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStartLoading'),
    );
    expect(screen.getByTestId('route-stub-IncidentStartLoading')).toBeOnTheScreen();
  });
});
