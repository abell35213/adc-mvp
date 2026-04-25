/**
 * RNTL coverage for `IncidentStartLoadingScreen`.
 *
 * Behaviours under test:
 *   1. Payload builder — assigned-vehicle resolution maps to
 *      `vehicle_strategy: 'last_assigned'` with no `qr_token`.
 *   2. Payload builder — QR-scan resolution maps to
 *      `vehicle_strategy: 'qr'` and forwards the `qr_token`.
 *   3. Payload builder — when no `navigator.geolocation` is present,
 *      `device_location` is `null`.
 *   4. Payload builder — geolocation success populates
 *      `device_location` with the converted ISO timestamp.
 *   5. Payload builder — geolocation error keeps `device_location`
 *      as `null` (caller swallows the error).
 *   6. Happy path — successful initiation transitions the workflow,
 *      completes the route, emits the `incident_initiated` analytics
 *      event, and replaces nav with `InstructionStep`.
 *   7. 409 duplicate with a recoverable active incident proceeds to
 *      `InstructionStep` silently.
 *   8. 409 duplicate without a recoverable incident surfaces the
 *      "Another active incident already exists…" copy.
 *   9. Network failure (`TypeError`) shows the ambiguous-recovery
 *      message; "Retry startup" re-issues the call and succeeds.
 *  10. Timeout error path matches the network-failure path.
 *  11. Generic 5xx error renders the server message verbatim and
 *      skips the active-incident lookup.
 *  12. Non-Error throwable falls back to the generic startup message.
 *  13. "Return home" button navigates back to `DriverHome`.
 *
 * `useProtocolFlow` is mocked at module level so that the screen's
 * effect — whose dependency chain reads `protocolContext` — sees a
 * stable seed across renders. The real provider mutates
 * `protocolContext` on every callback, which would cause the screen's
 * `beginIncidentInitiation` effect to re-fire mid-test as we seed it.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();
const mockTransitionWorkflow = jest.fn();
let mockVehicleMethod: 'assigned_vehicle' | 'qr_scan' = 'assigned_vehicle';
let mockQrToken: string | null = null;

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    initiateDriverIncident: jest.fn(),
    getDriverActiveIncident: jest.fn(),
  };
});
jest.mock('../../../navigation/useProtocolRouteGuard', () => ({
  useProtocolRouteGuard: jest.fn(),
}));
jest.mock('../../../navigation/ProtocolFlowContext', () => {
  const actual = jest.requireActual('../../../navigation/ProtocolFlowContext');
  return {
    ...actual,
    useProtocolFlow: () => ({
      completeRoute: mockCompleteRoute,
      transitionWorkflow: mockTransitionWorkflow,
      protocolContext: {
        workflowCorrelationId: 'wfc-1',
        vehicleResolutionMethod: mockVehicleMethod,
        qrToken: mockQrToken,
      },
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

import * as api from '../../../api';
import { ApiRequestError } from '../../../api';
import { emitProtocolAnalyticsEvent } from '../../../telemetry/protocolEvents';

import IncidentStartLoadingScreen from '../../../screens/IncidentStartLoadingScreen';
import { renderScreen } from '../test-utils';

const mockedInitiate = () => jest.mocked(api.initiateDriverIncident);
const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);

const SUCCESS_RESPONSE: api.DriverIncidentInitiateResponse = {
  incident_id: 'inc-1',
  safety_notified: true,
} as api.DriverIncidentInitiateResponse;

type GeoFix = {
  coords: {
    latitude: number;
    longitude: number;
    accuracy: number | null;
  };
  timestamp: number;
};

const installGeolocation = (
  fix: GeoFix | { error: true } | null,
) => {
  const root = globalThis as unknown as {
    navigator?: { geolocation?: unknown };
  };
  if (!root.navigator) {
    root.navigator = {};
  }
  if (fix === null) {
    root.navigator.geolocation = undefined;
    return;
  }
  root.navigator.geolocation = {
    getCurrentPosition: (
      onSuccess: (pos: GeoFix) => void,
      onError: () => void,
    ) => {
      if ('error' in fix && fix.error) {
        onError();
      } else {
        onSuccess(fix as GeoFix);
      }
    },
  };
};

const mountScreen = (opts: {
  vehicleResolution?: 'assigned_vehicle' | 'qr_scan';
  qrToken?: string | null;
} = {}) => {
  mockVehicleMethod = opts.vehicleResolution ?? 'assigned_vehicle';
  mockQrToken = opts.qrToken ?? null;
  return renderScreen({
    name: 'IncidentStartLoading',
    component: IncidentStartLoadingScreen,
    siblings: [
      { name: 'InstructionStep' },
      { name: 'DriverHome' },
      { name: 'SafetyGate' },
    ],
  });
};

describe('IncidentStartLoadingScreen', () => {
  beforeEach(() => {
    // The screen schedules a `setTimeout` for the initiation timeout
    // race; in real-timer mode it outlives the test and Jest force
    // exits the worker. Fake timers let the awaited
    // `initiateDriverIncident` resolve while the timeout is held so
    // teardown is clean.
    jest.useFakeTimers({ doNotFake: ['setImmediate', 'queueMicrotask'] });
    installGeolocation(null);
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  describe('payload builder', () => {
    it('uses last_assigned strategy with no qr_token when accepting the assigned vehicle', async () => {
      mockedInitiate().mockResolvedValueOnce(SUCCESS_RESPONSE);
      mountScreen({ vehicleResolution: 'assigned_vehicle' });

      await waitFor(() => {
        expect(mockedInitiate()).toHaveBeenCalledTimes(1);
      });
      const payload = mockedInitiate().mock.calls[0][0];
      expect(payload.vehicle_strategy).toBe('last_assigned');
      expect(payload.qr_token).toBeUndefined();
      expect(payload.device_location).toBeNull();
      expect(payload.device).toEqual(
        expect.objectContaining({ app: 'driver-app', captured_at: expect.any(String) }),
      );
    });

    it('uses qr strategy and forwards qrToken when the vehicle was scanned', async () => {
      mockedInitiate().mockResolvedValueOnce(SUCCESS_RESPONSE);
      mountScreen({ vehicleResolution: 'qr_scan', qrToken: 'TOK-9' });

      await waitFor(() => {
        expect(mockedInitiate()).toHaveBeenCalledTimes(1);
      });
      const payload = mockedInitiate().mock.calls[0][0];
      expect(payload.vehicle_strategy).toBe('qr');
      expect(payload.qr_token).toBe('TOK-9');
    });

    it('forwards a device_location when geolocation returns a fix', async () => {
      installGeolocation({
        coords: { latitude: 47.61, longitude: -122.33, accuracy: 25 },
        timestamp: 1700000000000,
      });
      mockedInitiate().mockResolvedValueOnce(SUCCESS_RESPONSE);
      mountScreen({ vehicleResolution: 'assigned_vehicle' });

      await waitFor(() => {
        expect(mockedInitiate()).toHaveBeenCalledTimes(1);
      });
      const payload = mockedInitiate().mock.calls[0][0];
      expect(payload.device_location).toEqual(
        expect.objectContaining({
          latitude: 47.61,
          longitude: -122.33,
          accuracy_meters: 25,
          timestamp_utc: new Date(1700000000000).toISOString(),
        }),
      );
    });

    it('forwards null device_location when geolocation errors', async () => {
      installGeolocation({ error: true });
      mockedInitiate().mockResolvedValueOnce(SUCCESS_RESPONSE);
      mountScreen({ vehicleResolution: 'assigned_vehicle' });

      await waitFor(() => {
        expect(mockedInitiate()).toHaveBeenCalledTimes(1);
      });
      expect(mockedInitiate().mock.calls[0][0].device_location).toBeNull();
    });
  });

  describe('happy path', () => {
    it('emits incident_initiated, transitions workflow, completes route, and replaces nav with InstructionStep', async () => {
      mockedInitiate().mockResolvedValueOnce(SUCCESS_RESPONSE);
      const { getNavigation } = mountScreen({
        vehicleResolution: 'assigned_vehicle',
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('InstructionStep');
      });
      expect(mockTransitionWorkflow).toHaveBeenCalledWith('incident_initiated');
      expect(mockCompleteRoute).toHaveBeenCalledWith('IncidentStartLoading');
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'incident_initiated',
        expect.objectContaining({
          payload: expect.objectContaining({
            vehicle_resolution_method: 'assigned_vehicle',
          }),
        }),
      );
    });
  });

  describe('error paths', () => {
    it('409 duplicate with a recoverable active incident proceeds to InstructionStep silently', async () => {
      mockedInitiate().mockRejectedValueOnce(
        new ApiRequestError('active incident already exists', 409),
      );
      mockedActiveIncident().mockResolvedValueOnce({
        incident_id: 'inc-existing',
        status: 'open',
      } as api.DriverActiveIncidentResponse);
      const { getNavigation } = mountScreen();

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('InstructionStep');
      });
      expect(
        screen.queryByText(/Another active incident already exists/i),
      ).toBeNull();
    });

    it('409 duplicate with no recoverable incident surfaces the duplicate message', async () => {
      mockedInitiate().mockRejectedValueOnce(
        new ApiRequestError('active incident already exists', 409),
      );
      mockedActiveIncident().mockResolvedValueOnce(null);
      mountScreen();

      expect(
        await screen.findByText(/Another active incident already exists/i),
      ).toBeOnTheScreen();
      expect(screen.getByText('Retry startup')).toBeOnTheScreen();
      expect(screen.getByText('Return home')).toBeOnTheScreen();
    });

    it('network failure (TypeError) shows the ambiguous-recovery message and Retry re-issues the call', async () => {
      mockedActiveIncident().mockResolvedValue(null);
      mockedInitiate()
        .mockRejectedValueOnce(new TypeError('Network request failed'))
        .mockResolvedValueOnce(SUCCESS_RESPONSE);
      const { getNavigation } = mountScreen();

      expect(
        await screen.findByText(
          /Unable to confirm incident startup after timeout\/network failure/i,
        ),
      ).toBeOnTheScreen();

      await act(async () => {
        fireEvent.press(screen.getByText('Retry startup'));
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('InstructionStep');
      });
      expect(mockedInitiate()).toHaveBeenCalledTimes(2);
    });

    it('timeout error (`/timed out/`) routes through ambiguous recovery', async () => {
      mockedActiveIncident().mockResolvedValueOnce(null);
      mockedInitiate().mockRejectedValueOnce(new Error('Request timed out.'));
      mountScreen();

      expect(
        await screen.findByText(
          /Unable to confirm incident startup after timeout\/network failure/i,
        ),
      ).toBeOnTheScreen();
    });

    it('generic 5xx error renders the server message and skips ambiguous recovery', async () => {
      mockedInitiate().mockRejectedValueOnce(
        new ApiRequestError('Internal server error.', 500),
      );
      mountScreen();

      expect(
        await screen.findByText('Internal server error.'),
      ).toBeOnTheScreen();
      // Active-incident lookup is reserved for ambiguous/duplicate
      // failures only.
      expect(mockedActiveIncident()).not.toHaveBeenCalled();
    });

    it('falls back to the generic startup message for non-Error throwables', async () => {
      mockedInitiate().mockRejectedValueOnce('boom');
      mountScreen();

      expect(
        await screen.findByText('Unable to start incident protocol. Please retry.'),
      ).toBeOnTheScreen();
    });

    it('Return home navigates back to DriverHome after a failure', async () => {
      mockedInitiate().mockRejectedValueOnce(
        new ApiRequestError('Bad request', 422),
      );
      const { getNavigation } = mountScreen();

      await screen.findByText('Bad request');
      await act(async () => {
        fireEvent.press(screen.getByText('Return home'));
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
      });
    });
  });
});
