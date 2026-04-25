/**
 * RNTL coverage for `IncidentConfirmScreen`.
 *
 * Behaviours under test:
 *   1. Continue happy path:
 *      - `transitionWorkflow('incident_confirmed')` is invoked
 *      - timeline+analytics event `driver_protocol_launch_confirmed`
 *        is emitted
 *      - the route is marked complete (`completeRoute('IncidentConfirm')`)
 *      - navigation lands on `VehicleConfirm`
 *   2. Cancel → navigation goes to `DriverHome`.
 *   3. Snapshot of the rendered step.
 *
 * The protocol-flow context is the *real* provider — we drive it
 * through `startProtocol()` so the workflow guard
 * (`incident_confirmed` requires `isAuthenticated`) is satisfied —
 * and a `ProtocolFlowSpy` controller reads back the live state to
 * confirm the side effects.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

jest.mock('../../../navigation/useProtocolRouteGuard', () => ({
  useProtocolRouteGuard: jest.fn(),
}));
jest.mock('../../../telemetry/protocolEvents', () => {
  const actual = jest.requireActual('../../../telemetry/protocolEvents');
  return {
    ...actual,
    emitProtocolAnalyticsEvent: jest.fn(),
    emitTimelineAndAnalyticsEvent: jest.fn(),
  };
});

import {
  emitTimelineAndAnalyticsEvent,
} from '../../../telemetry/protocolEvents';
import IncidentConfirmScreen from '../../../screens/IncidentConfirmScreen';
import {
  ProtocolFlowSpy,
  createProtocolFlowController,
  renderScreen,
} from '../test-utils';

const mountScreen = () => {
  const controller = createProtocolFlowController();
  const result = renderScreen({
    name: 'IncidentConfirm',
    component: IncidentConfirmScreen,
    siblings: [{ name: 'VehicleConfirm' }, { name: 'DriverHome' }],
    providerOptions: {
      innerWrapper: (children) => (
        <>
          <ProtocolFlowSpy controller={controller} />
          {children}
        </>
      ),
    },
  });
  // The route guard requires `isAuthenticated`. Drive the real
  // provider through `startProtocol()` so the workflow guard for the
  // `authenticated → incident_confirmed` transition is satisfied.
  act(() => {
    controller.current?.startProtocol();
  });
  return { ...result, controller };
};

describe('IncidentConfirmScreen', () => {
  it('renders the step title and description', () => {
    mountScreen();
    expect(screen.getByText('Confirm Incident')).toBeOnTheScreen();
    expect(
      screen.getByText(/Confirm this is the right moment to launch the incident protocol/i),
    ).toBeOnTheScreen();
  });

  it('Continue transitions the workflow, emits analytics, marks the route complete, and navigates to VehicleConfirm', async () => {
    const { getNavigation, controller } = mountScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Continue'));
    });

    await waitFor(() => {
      expect(controller.current?.workflowState).toBe('incident_confirmed');
    });
    expect(controller.current?.completedRoutes.has('IncidentConfirm')).toBe(true);
    expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith(
      'driver_protocol_launch_confirmed',
    );
    await waitFor(() => {
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('VehicleConfirm');
    });
  });

  it('Cancel navigates back to DriverHome without modifying protocol state', async () => {
    const { getNavigation, controller } = mountScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Cancel'));
    });

    expect(emitTimelineAndAnalyticsEvent).not.toHaveBeenCalled();
    expect(controller.current?.completedRoutes.has('IncidentConfirm')).toBe(false);
    await waitFor(() => {
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
    });
  });

  it('matches the rendered snapshot', () => {
    const { screen: rendered } = mountScreen();
    expect(rendered.toJSON()).toMatchSnapshot();
  });
});
