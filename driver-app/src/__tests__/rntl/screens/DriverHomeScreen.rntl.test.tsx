/**
 * RNTL coverage for `DriverHomeScreen`.
 *
 * Behaviours under test:
 *   1. On focus, `getDriverMe` + `getDriverActiveIncident` are both
 *      called and the resolved driver name / phone / vehicle label are
 *      rendered. Vehicle falls back to "Unassigned" when missing.
 *   2. API failures surface in the HelperText. Covers `ApiRequestError`,
 *      generic `Error`, and non-Error throwables.
 *   3. "Start Incident Protocol" with no resumable state →
 *      `startProtocol` is invoked on the protocol-flow context, an
 *      analytics event is emitted, and navigation lands on
 *      `IncidentConfirm`. No `Alert` is shown.
 *   4. "Start Incident Protocol" with resumable state → `Alert.alert` is
 *      shown with Cancel / Resume / Discard buttons.
 *      4a. Cancel → no state change, no navigation.
 *      4b. Resume → `restoreProtocol(completedRoutes)`, analytics event
 *          carrying the correct `resume_route`, navigation to the first
 *          incomplete route (`getFirstIncompleteRoute`).
 *      4c. Discard → drafts + resume keys are cleared, `resetProtocol`
 *          is called, then a fresh protocol starts on `IncidentConfirm`.
 *   5. Resume route fallback to `IncidentStatus` when the only resumable
 *      signal is an active incident (no drafts, no completed routes).
 *   6. "Scan Vehicle QR" navigates to `QrScan`.
 *   7. Resume card is visible iff `activeIncident.incident_id` is set
 *      and tapping its inner "Resume Incident" button drives the same
 *      resume path.
 *   8. Snapshot of the loaded state.
 *
 * The protocol flow context is consumed via the *real* provider (so the
 * actual `startProtocol` / `restoreProtocol` / `resetProtocol`
 * implementations run), and a `ProtocolFlowSpy` reads the live snapshot
 * to assert state transitions.
 */

import { Alert } from 'react-native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

jest.mock('../../../api');
jest.mock('../../../telemetry/protocolEvents', () => {
  const actual = jest.requireActual('../../../telemetry/protocolEvents');
  return {
    ...actual,
    emitProtocolAnalyticsEvent: jest.fn(),
  };
});

import * as api from '../../../api';
import { emitProtocolAnalyticsEvent } from '../../../telemetry/protocolEvents';

import DriverHomeScreen from '../../../screens/DriverHomeScreen';
import {
  PROTOCOL_RESUME_STORAGE_KEY,
} from '../../../store/protocolResumeStore';
import AsyncStorage from '../../mocks/asyncStorage';
import {
  ProtocolFlowSpy,
  apiError,
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
  display_name: 'Grace Hopper',
  vehicle: null,
};

const ACTIVE_INCIDENT: api.DriverActiveIncidentResponse = {
  incident_id: 'inc-77',
  status: 'in_progress',
};

// Suppress noisy log output from the resume store's dev warning path.
const originalConsoleWarn = console.warn;
beforeAll(() => {
  console.warn = jest.fn();
});
afterAll(() => {
  console.warn = originalConsoleWarn;
});

beforeEach(() => {
  AsyncStorage.__reset();
});

const mountScreen = () => {
  const controller = createProtocolFlowController();
  const result = renderScreen({
    name: 'DriverHome',
    component: DriverHomeScreen,
    siblings: [
      { name: 'IncidentConfirm' },
      { name: 'IncidentStartLoading' },
      { name: 'IncidentStatus' },
      { name: 'QrScan' },
      { name: 'SceneFacts' },
      { name: 'InstructionStep' },
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
  return { ...result, controller };
};

describe('DriverHomeScreen', () => {
  describe('initial load', () => {
    it('renders the driver display name, phone, and vehicle label on focus', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      mountScreen();

      expect(await screen.findByText('Ada Lovelace • +15551234567')).toBeOnTheScreen();
      expect(screen.getByText('Truck 42')).toBeOnTheScreen();
      expect(mockedApi(api).getDriverMe).toHaveBeenCalledTimes(1);
      expect(mockedApi(api).getDriverActiveIncident).toHaveBeenCalledTimes(1);
    });

    it('falls back to "Unassigned" when the driver has no vehicle', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITHOUT_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      mountScreen();

      expect(await screen.findByText('Unassigned')).toBeOnTheScreen();
    });

    it('shows the resume card only when an active incident is present', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(ACTIVE_INCIDENT);

      mountScreen();

      expect(
        await screen.findByText('Incident #inc-77 is currently in_progress.'),
      ).toBeOnTheScreen();
    });

    it('hides the resume card when there is no active incident', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      mountScreen();

      // Wait for load to complete.
      await screen.findByText('Truck 42');
      expect(screen.queryByText(/is currently/)).toBeNull();
    });
  });

  describe('error handling', () => {
    it.each([
      ['ApiRequestError', () => apiError(500, 'driver service down')],
      ['Error', () => new Error('Network request failed')],
    ])('surfaces %s.message in the HelperText when getDriverMe rejects', async (_label, build) => {
      mockedApi(api).getDriverMe.mockRejectedValueOnce(build());
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      mountScreen();

      const message = (build() as Error).message;
      expect(await screen.findByText(message)).toBeOnTheScreen();
    });

    it('falls back to a generic message for non-Error throwables', async () => {
      mockedApi(api).getDriverMe.mockRejectedValueOnce('boom');
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      mountScreen();

      expect(await screen.findByText('Unable to load home data.')).toBeOnTheScreen();
    });

    it('surfaces a getDriverActiveIncident failure', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockRejectedValueOnce(
        apiError(503, 'incident service unavailable'),
      );

      mountScreen();

      expect(await screen.findByText('incident service unavailable')).toBeOnTheScreen();
    });
  });

  describe('Start Incident Protocol — no resumable state', () => {
    beforeEach(() => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);
    });

    it('starts a fresh protocol and navigates to IncidentConfirm without prompting', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert');
      const { getNavigation, controller } = mountScreen();

      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Start Incident Protocol'));
      });

      expect(alertSpy).not.toHaveBeenCalled();
      // `startProtocol` resets state and stamps a new workflow correlation id.
      await waitFor(() => {
        expect(controller.current?.protocolContext.isAuthenticated).toBe(true);
      });
      expect(controller.current?.protocolContext.workflowCorrelationId).toEqual(
        expect.any(String),
      );
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith('protocol_start_tapped');
      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentConfirm');
      });

      alertSpy.mockRestore();
    });

    it('navigates to QrScan when "Scan Vehicle QR" is tapped', async () => {
      const { getNavigation } = mountScreen();
      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Scan Vehicle QR'));
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('QrScan');
      });
    });
  });

  describe('Start Incident Protocol — resumable state', () => {
    /**
     * Helper: pretend the user already filled in the SceneFacts draft.
     * This makes `resolveProtocolResumeState` infer that
     * `IncidentConfirm`, `VehicleConfirm`, `SafetyGate`, and
     * `InstructionStep` are complete on the next load.
     *
     * We seed a draft (rather than the resume-state key) because the
     * `ProtocolFlowProvider` overwrites the resume key with the
     * provider's empty `completedRoutes` on mount, which would clobber
     * any direct seed of that key.
     */
    const seedSceneFactsDraft = async () => {
      await AsyncStorage.setItem(
        'driver_scene_facts_draft_v1',
        JSON.stringify({ incidentId: 'inc-77' }),
      );
    };

    beforeEach(async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(ACTIVE_INCIDENT);
      await seedSceneFactsDraft();
    });

    /**
     * Walks the rendered Alert dialog by `text` and synchronously fires
     * its `onPress` handler. `Alert.alert` is mocked at the module level
     * because RN does not render a real dialog under jsdom.
     */
    const pressAlertButton = (alertSpy: jest.SpyInstance, text: string) => {
      const lastCall = alertSpy.mock.calls.at(-1);
      const buttons = lastCall?.[2] as Array<{ text?: string; onPress?: () => void }>;
      const target = buttons.find((button) => button.text === text);
      expect(target).toBeDefined();
      act(() => {
        target?.onPress?.();
      });
    };

    it('opens the resume Alert with Cancel / Resume / Discard buttons', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
      mountScreen();
      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Start Incident Protocol'));
      });

      expect(alertSpy).toHaveBeenCalledTimes(1);
      const [title, , buttons] = alertSpy.mock.calls[0];
      expect(title).toBe('Resume previous protocol?');
      expect((buttons as Array<{ text: string }>).map((b) => b.text)).toEqual([
        'Cancel',
        'Resume',
        'Discard and start new',
      ]);

      alertSpy.mockRestore();
    });

    it('Cancel closes the dialog without changing state or navigating', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
      const { getNavigation } = mountScreen();
      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Start Incident Protocol'));
      });
      pressAlertButton(alertSpy, 'Cancel');

      // Cancel has no onPress; we still verify nothing changed.
      expect(emitProtocolAnalyticsEvent).not.toHaveBeenCalled();
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');

      alertSpy.mockRestore();
    });

    it('Resume restores completed routes, emits analytics, and navigates to the next incomplete route', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
      const { getNavigation, controller } = mountScreen();
      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Start Incident Protocol'));
      });
      pressAlertButton(alertSpy, 'Resume');

      // Four routes were inferred-complete from the SceneFacts draft
      // (IncidentConfirm, VehicleConfirm, SafetyGate, InstructionStep).
      // `PROTOCOL_ROUTE_ORDER` places `IncidentStartLoading` between
      // `SafetyGate` and `InstructionStep`, so the first incomplete
      // route reported by `getFirstIncompleteRoute` is
      // `IncidentStartLoading`.
      await waitFor(() => {
        expect(controller.current?.completedRoutes.size).toBe(4);
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'protocol_resumed',
        expect.objectContaining({
          incidentId: 'inc-77',
          payload: { resume_route: 'IncidentStartLoading' },
        }),
      );
      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStartLoading');
      });

      alertSpy.mockRestore();
    });

    it('Discard clears drafts + resume state, resets the protocol, and starts a new one', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
      const { getNavigation, controller } = mountScreen();
      await screen.findByText('Truck 42');

      await act(async () => {
        fireEvent.press(screen.getByText('Start Incident Protocol'));
      });
      await act(async () => {
        pressAlertButton(alertSpy, 'Discard and start new');
      });

      await waitFor(async () => {
        expect(await AsyncStorage.getItem(PROTOCOL_RESUME_STORAGE_KEY)).toBeTruthy();
        // After reset the persisted payload should hold an empty
        // completedRoutes array (the provider re-persists on every
        // change).
        const raw = await AsyncStorage.getItem(PROTOCOL_RESUME_STORAGE_KEY);
        const parsed = JSON.parse(raw as string);
        expect(parsed.completedRoutes).toEqual([]);
      });
      await waitFor(() => {
        expect(controller.current?.completedRoutes.size).toBe(0);
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith('protocol_start_tapped');
      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentConfirm');
      });

      alertSpy.mockRestore();
    });
  });

  describe('Resume Incident card', () => {
    it('falls back to IncidentStatus when only an active incident exists with no completed routes', async () => {
      const alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(ACTIVE_INCIDENT);

      const { getNavigation } = mountScreen();
      await screen.findByText('Incident #inc-77 is currently in_progress.');

      // "Resume Incident" appears twice on screen — once as the card
      // title and once as the button label. The button is the last
      // match (rendered after the title).
      const matches = screen.getAllByText('Resume Incident');
      await act(async () => {
        fireEvent.press(matches[matches.length - 1]);
      });

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStatus');
      });
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'protocol_resumed',
        expect.objectContaining({
          incidentId: 'inc-77',
          payload: { resume_route: 'IncidentStatus' },
        }),
      );

      alertSpy.mockRestore();
    });
  });

  describe('snapshot', () => {
    it('matches the rendered snapshot when fully loaded', async () => {
      mockedApi(api).getDriverMe.mockResolvedValueOnce(DRIVER_WITH_VEHICLE);
      mockedApi(api).getDriverActiveIncident.mockResolvedValueOnce(null);

      const { screen: rendered } = mountScreen();
      await screen.findByText('Truck 42');

      expect(rendered.toJSON()).toMatchSnapshot();
    });
  });
});
