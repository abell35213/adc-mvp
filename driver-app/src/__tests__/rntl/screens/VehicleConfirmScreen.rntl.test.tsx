/**
 * RNTL coverage for `VehicleConfirmScreen`.
 *
 * Behaviours under test:
 *   1. Loads `getDriverMe` on focus and renders the assigned-vehicle
 *      label, or the "No assigned vehicle found…" copy if missing.
 *   2. Surfaces `getDriverMe` errors in the load HelperText.
 *   3. "Accept assigned vehicle" → `resolveVehicle({method:'assigned_vehicle'})`,
 *      shows the resolution summary, and enables the continue button.
 *   4. "Resolve QR vehicle" with empty input → invalid status + message,
 *      no call to `resolveVehicleQr`.
 *   5. "Resolve QR vehicle" happy path:
 *      - Emits `qr_scan_started` then `qr_scan_success` analytics
 *      - Calls `resolveVehicle({method:'qr_scan'})`
 *      - Renders the success message
 *   6. "Resolve QR vehicle" → 400 ApiRequestError → `qr_scan_failed`
 *      analytics with `invalid_token: true`, "Retry QR resolution"
 *      button shown which clears the input on tap.
 *   7. "Resolve QR vehicle" → non-400 error → `qr_scan_failed` with
 *      `invalid_token: false`, no retry button.
 *   8. Continue button is disabled until the vehicle is resolved;
 *      after resolution it emits `vehicle_confirmed` analytics, marks
 *      the route complete, and navigates to `SafetyGate`.
 *   9. Back navigates back.
 *  10. Snapshot of the loaded state with an assigned vehicle.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { TextInput as RNTextInput } from 'react-native';

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverMe: jest.fn(),
    getDriverActiveIncident: jest.fn(),
  };
});
jest.mock('../../../services/incidents');
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

import * as api from '../../../api';
import * as incidentsService from '../../../services/incidents';
import { emitProtocolAnalyticsEvent } from '../../../telemetry/protocolEvents';

import VehicleConfirmScreen from '../../../screens/VehicleConfirmScreen';
import {
  apiError,
  ProtocolFlowSpy,
  createProtocolFlowController,
  mockedApi,
  renderScreen,
} from '../test-utils';

const DRIVER_WITH_VEHICLE: api.DriverMeResponse = {
  driver_id: 'drv-1',
  org_id: 'org-1',
  phone_e164: '+15551234567',
  display_name: 'Ada Lovelace',
  vehicle: {
    adc_vehicle_id: 'veh-1',
    display_label: 'Truck 42',
  },
};

const DRIVER_WITHOUT_VEHICLE: api.DriverMeResponse = {
  ...DRIVER_WITH_VEHICLE,
  vehicle: null,
};

const mockedIncidents = () =>
  jest.mocked(incidentsService) as jest.Mocked<typeof incidentsService>;

const mountScreen = () => {
  const controller = createProtocolFlowController();
  const result = renderScreen({
    name: 'VehicleConfirm',
    component: VehicleConfirmScreen,
    siblings: [
      { name: 'IncidentConfirm' },
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
  // `useProtocolRouteGuard` is mocked at the module level so this
  // screen renders without needing a seeded `completedRoutes`. We
  // still kick off `startProtocol()` so the protocol context starts
  // as authenticated (matching how the real provider arrives here
  // from `IncidentConfirm`).
  act(() => {
    controller.current?.startProtocol();
  });
  return { ...result, controller };
};

const getQrInput = () => screen.UNSAFE_getByType(RNTextInput);

describe('VehicleConfirmScreen', () => {
  describe('initial load', () => {
    it('renders the assigned-vehicle copy when the driver has a vehicle', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mountScreen();

      expect(await screen.findByText('Truck 42 (veh-1)')).toBeOnTheScreen();
    });

    it('renders the "no assigned vehicle" fallback when the driver has none', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITHOUT_VEHICLE);
      mountScreen();

      expect(
        await screen.findByText('No assigned vehicle found for this driver.'),
      ).toBeOnTheScreen();
    });

    it('surfaces a getDriverMe failure in the load HelperText', async () => {
      mockedApi(api).getDriverMe.mockRejectedValueOnce(
        apiError(500, 'driver service down'),
      );
      mountScreen();

      expect(await screen.findByText('driver service down')).toBeOnTheScreen();
    });

    it('falls back to a generic load error for non-Error throwables', async () => {
      mockedApi(api).getDriverMe.mockRejectedValueOnce('boom');
      mountScreen();

      expect(
        await screen.findByText('Unable to load assigned vehicle.'),
      ).toBeOnTheScreen();
    });
  });

  describe('Accept assigned vehicle', () => {
    it('resolves the assigned vehicle and enables the continue button', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      const { controller } = mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.press(screen.getByText('Accept assigned vehicle'));
      });

      await waitFor(() => {
        expect(controller.current?.protocolContext.vehicleResolved).toBe(true);
      });
      expect(controller.current?.protocolContext.vehicleResolutionMethod).toBe(
        'assigned_vehicle',
      );
      expect(controller.current?.protocolContext.vehicleId).toBe('veh-1');
      expect(screen.getByText('Using assigned vehicle veh-1.')).toBeOnTheScreen();
    });

    it('does nothing when there is no assigned vehicle', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITHOUT_VEHICLE);
      const { controller } = mountScreen();
      await screen.findByText('No assigned vehicle found for this driver.');

      await act(async () => {
        fireEvent.press(screen.getByText('Accept assigned vehicle'));
      });

      expect(controller.current?.protocolContext.vehicleResolved).toBe(false);
    });
  });

  describe('Resolve QR vehicle', () => {
    beforeEach(() => {
      mockedApi(api).getDriverMe.mockResolvedValue(DRIVER_WITH_VEHICLE);
    });

    it('shows an invalid message when the QR token is empty', async () => {
      mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.press(screen.getByText('Resolve QR vehicle'));
      });

      expect(screen.getByText('Enter a QR token before resolving.')).toBeOnTheScreen();
      expect(mockedIncidents().resolveVehicleQr).not.toHaveBeenCalled();
      // The invalid-token retry button is rendered in this status too.
      expect(screen.getByText('Retry QR resolution')).toBeOnTheScreen();
    });

    it('happy path emits start+success analytics, resolves the vehicle, and shows the success message', async () => {
      mockedIncidents().resolveVehicleQr.mockResolvedValueOnce({
        adc_vehicle_id: 'veh-9',
        display_label: 'Truck 9',
      });
      const { controller } = mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.changeText(getQrInput(), '  TOKEN-123  ');
      });
      await act(async () => {
        fireEvent.press(screen.getByText('Resolve QR vehicle'));
      });

      await waitFor(() => {
        expect(controller.current?.protocolContext.vehicleResolved).toBe(true);
      });
      expect(mockedIncidents().resolveVehicleQr).toHaveBeenCalledWith('TOKEN-123');
      expect(controller.current?.protocolContext.vehicleResolutionMethod).toBe('qr_scan');
      expect(controller.current?.protocolContext.vehicleId).toBe('veh-9');
      expect(controller.current?.protocolContext.qrToken).toBe('TOKEN-123');

      const analyticsCalls = (
        emitProtocolAnalyticsEvent as jest.Mock
      ).mock.calls.map((call) => call[0]);
      expect(analyticsCalls).toEqual(
        expect.arrayContaining(['qr_scan_started', 'qr_scan_success']),
      );
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'qr_scan_success',
        expect.objectContaining({
          payload: expect.objectContaining({ vehicle_id: 'veh-9' }),
        }),
      );
      expect(screen.getByText('QR resolved Truck 9.')).toBeOnTheScreen();
    });

    it('400 ApiRequestError marks the token invalid and renders the retry button', async () => {
      mockedIncidents().resolveVehicleQr.mockRejectedValueOnce(
        apiError(400, 'invalid token'),
      );
      mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.changeText(getQrInput(), 'BAD');
      });
      await act(async () => {
        fireEvent.press(screen.getByText('Resolve QR vehicle'));
      });

      await waitFor(() => {
        expect(screen.getByText('invalid token')).toBeOnTheScreen();
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'qr_scan_failed',
        expect.objectContaining({
          payload: expect.objectContaining({ invalid_token: true }),
        }),
      );
      // Retry button clears state + input on tap.
      await act(async () => {
        fireEvent.press(screen.getByText('Retry QR resolution'));
      });
      expect(screen.queryByText('invalid token')).toBeNull();
      // Input should be cleared as a side-effect of the retry button.
      expect(getQrInput().props.value).toBe('');
    });

    it('non-400 error is reported as a generic failure (no retry button)', async () => {
      mockedIncidents().resolveVehicleQr.mockRejectedValueOnce(
        apiError(503, 'service down'),
      );
      mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.changeText(getQrInput(), 'TOK');
      });
      await act(async () => {
        fireEvent.press(screen.getByText('Resolve QR vehicle'));
      });

      await waitFor(() => {
        expect(screen.getByText('service down')).toBeOnTheScreen();
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'qr_scan_failed',
        expect.objectContaining({
          payload: expect.objectContaining({ invalid_token: false }),
        }),
      );
      // 'failed' status does not render the retry-button affordance.
      expect(screen.queryByText('Retry QR resolution')).toBeNull();
    });

    it('falls back to a generic message for non-Error throwables', async () => {
      mockedIncidents().resolveVehicleQr.mockRejectedValueOnce('weird');
      mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      await act(async () => {
        fireEvent.changeText(getQrInput(), 'TOK');
      });
      await act(async () => {
        fireEvent.press(screen.getByText('Resolve QR vehicle'));
      });

      await waitFor(() => {
        expect(
          screen.getByText('Unable to resolve vehicle QR token.'),
        ).toBeOnTheScreen();
      });
    });
  });

  describe('Continue and Back', () => {
    it('Continue is a no-op until the vehicle is resolved, then emits analytics + completes route + navigates to SafetyGate', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      const { controller, getNavigation } = mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      // Initially the continue button is disabled — pressing it
      // should not advance the workflow.
      await act(async () => {
        fireEvent.press(screen.getByText('Vehicle confirmed'));
      });
      expect(controller.current?.completedRoutes.has('VehicleConfirm')).toBe(false);

      await act(async () => {
        fireEvent.press(screen.getByText('Accept assigned vehicle'));
      });
      await waitFor(() =>
        expect(controller.current?.protocolContext.vehicleResolved).toBe(true),
      );

      await act(async () => {
        fireEvent.press(screen.getByText('Vehicle confirmed'));
      });

      await waitFor(() => {
        expect(controller.current?.completedRoutes.has('VehicleConfirm')).toBe(true);
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'vehicle_confirmed',
        expect.objectContaining({
          payload: expect.objectContaining({
            vehicle_resolution_method: 'assigned_vehicle',
            vehicle_id: 'veh-1',
          }),
        }),
      );
      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('SafetyGate');
      });
    });

    it('Back invokes navigation.goBack', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      // Mount with two screens in the stack so goBack has somewhere to land.
      const { getNavigation, controller } = mountScreen();
      await screen.findByText('Truck 42 (veh-1)');
      // Push another route then come back via goBack.
      act(() => getNavigation()?.navigate('SafetyGate'));
      await waitFor(() =>
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('SafetyGate'),
      );
      act(() => getNavigation()?.navigate('VehicleConfirm'));
      await waitFor(() =>
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('VehicleConfirm'),
      );

      await act(async () => {
        fireEvent.press(screen.getByText('Back'));
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('SafetyGate');
      });
      // sanity: route progress was not modified by Back.
      expect(controller.current?.completedRoutes.has('VehicleConfirm')).toBe(false);
    });
  });

  describe('snapshot', () => {
    it('matches the rendered snapshot when loaded with an assigned vehicle', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      const { screen: rendered } = mountScreen();
      await screen.findByText('Truck 42 (veh-1)');

      expect(rendered.toJSON()).toMatchSnapshot();
    });
  });
});
