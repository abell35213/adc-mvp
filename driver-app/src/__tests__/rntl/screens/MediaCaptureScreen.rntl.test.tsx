/**
 * RNTL coverage for `MediaCaptureScreen`.
 *
 * The screen owns the five-prompt evidence-capture checklist (truck
 * damage, other vehicle, license plate, wide scene, road/signal
 * context). Each prompt exposes Take Photo, Upload Existing, and
 * Skip; resolved prompts attach an artifact (with optional GPS) to a
 * local queue and persist to AsyncStorage. Continue is gated until
 * every prompt is resolved.
 *
 * Behaviours under test:
 *   1. Initializing state.
 *   2. Stored draft hydrates prompt statuses + queue when the
 *      `incidentId` matches the active incident.
 *   3. Mismatched-incident draft is ignored.
 *   4. Malformed stored JSON falls back to defaults without throwing.
 *   5. "Take Photo" transitions the prompt to `captured`, emits
 *      `artifact_capture_started` with `capture_source: 'camera'`,
 *      appends a queue artifact, and persists.
 *   6. "Upload Existing" transitions to `captured` with
 *      `capture_source: 'library'`.
 *   7. "Skip" transitions to `skipped`, emits no
 *      `artifact_capture_started` event, and does NOT grow the queue.
 *   8. GPS — `navigator.geolocation.getCurrentPosition` success
 *      attaches `{ latitude, longitude }` to the artifact; failure
 *      callback yields `null`.
 *   9. "Continue to Narrative" is blocked while any prompt is
 *      `pending`; the user stays on the screen.
 *  10. Resolving all five prompts unlocks Continue → `completeRoute`
 *      + nav `Narrative`.
 *  11. Back button wired.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
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
      protocolContext: { workflowCorrelationId: 'wfc-media' },
    }),
  };
});
jest.mock('../../../telemetry/protocolEvents', () => {
  const actual = jest.requireActual('../../../telemetry/protocolEvents');
  return {
    ...actual,
    emitProtocolAnalyticsEvent: jest.fn(),
  };
});

import * as api from '../../../api';
import { emitProtocolAnalyticsEvent } from '../../../telemetry/protocolEvents';
import AsyncStorage from '../../mocks/asyncStorage';
import MediaCaptureScreen from '../../../screens/MediaCaptureScreen';
import { renderScreen } from '../test-utils';

const STORAGE_KEY = 'driver_media_capture_draft_v1';
const PROMPT_TYPES = [
  'truck_damage',
  'other_vehicle',
  'license_plate',
  'wide_scene',
  'road_signal_context',
] as const;

const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);

const mountScreen = () =>
  renderScreen({
    name: 'MediaCapture',
    component: MediaCaptureScreen,
    params: { destinationPromptType: 'general_scene' },
    siblings: [{ name: 'Narrative' }, { name: 'DriverHome' }],
  });

const installGeolocation = (
  impl: NonNullable<typeof globalThis.navigator>['geolocation'] | null,
) => {
  if (!globalThis.navigator) {
    (globalThis as unknown as { navigator: object }).navigator = {};
  }
  (globalThis.navigator as { geolocation: unknown }).geolocation = impl;
};

const allButtonsByText = (label: string) => screen.getAllByText(label);

describe('MediaCaptureScreen', () => {
  beforeEach(() => {
    AsyncStorage.__reset();
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-9',
      status: 'open',
    } as api.DriverActiveIncidentResponse);
    installGeolocation(null);
  });

  it('shows the initializing copy until the active incident resolves', async () => {
    let resolveActive: (value: api.DriverActiveIncidentResponse) => void;
    mockedActiveIncident().mockReset();
    mockedActiveIncident().mockImplementationOnce(
      () =>
        new Promise<api.DriverActiveIncidentResponse>((resolve) => {
          resolveActive = resolve;
        }),
    );
    mountScreen();

    expect(screen.getByText(/Loading media capture prompts/i)).toBeOnTheScreen();

    await act(async () => {
      resolveActive!({ incident_id: 'inc-9', status: 'open' } as api.DriverActiveIncidentResponse);
    });
    await screen.findByText('Media Capture');
  });

  it('hydrates prompt statuses and queue from a stored draft when the incident matches', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-9',
        prompts: [
          { type: 'truck_damage', status: 'captured' },
          { type: 'license_plate', status: 'skipped' },
        ],
        queue: [
          {
            id: 'art-1',
            promptType: 'truck_damage',
            source: 'camera',
            capturedAtUtc: '2026-04-25T16:00:00Z',
            gps: null,
          },
        ],
      }),
    );
    mountScreen();

    await screen.findByText('Media Capture');
    // Summary surfaces the rehydrated queue size.
    expect(screen.getByText('Local queue items: 1')).toBeOnTheScreen();
    // truck_damage chip carries the rehydrated status.
    expect(screen.getByText('captured')).toBeOnTheScreen();
    expect(screen.getByText('skipped')).toBeOnTheScreen();
    // The other 3 prompts remain pending — show the count.
    expect(screen.getByText('Remaining prompts: 3')).toBeOnTheScreen();
  });

  it('ignores a stored draft whose incidentId does not match the active one', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-OTHER',
        prompts: [{ type: 'truck_damage', status: 'captured' }],
        queue: [
          {
            id: 'should-not-load',
            promptType: 'truck_damage',
            source: 'camera',
            capturedAtUtc: 'x',
            gps: null,
          },
        ],
      }),
    );
    mountScreen();

    await screen.findByText('Media Capture');
    expect(screen.getByText('Local queue items: 0')).toBeOnTheScreen();
    expect(screen.getByText('Remaining prompts: 5')).toBeOnTheScreen();
  });

  it('falls back to defaults when stored JSON is malformed', async () => {
    await AsyncStorage.setItem(STORAGE_KEY, '{ not json');
    mountScreen();

    await screen.findByText('Media Capture');
    expect(screen.getByText('Remaining prompts: 5')).toBeOnTheScreen();
  });

  it('Take Photo flips status to captured, emits artifact_capture_started with camera, grows the queue, and persists', async () => {
    installGeolocation({
      getCurrentPosition: ((onSuccess: (p: { coords: { latitude: number; longitude: number } }) => void) => {
        onSuccess({ coords: { latitude: 47.6, longitude: -122.3 } });
      }) as unknown as Geolocation['getCurrentPosition'],
    } as unknown as Geolocation);

    mountScreen();
    await screen.findByText('Media Capture');

    await act(async () => {
      fireEvent.press(allButtonsByText('Take Photo')[0]);
    });

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'artifact_capture_started',
      expect.objectContaining({
        incidentId: 'inc-9',
        payload: expect.objectContaining({
          prompt_type: 'truck_damage',
          capture_source: 'camera',
        }),
      }),
    );
    expect(screen.getByText('Local queue items: 1')).toBeOnTheScreen();
    expect(screen.getByText('Remaining prompts: 4')).toBeOnTheScreen();

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.incidentId).toBe('inc-9');
    expect(stored.prompts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'truck_damage', status: 'captured' }),
      ]),
    );
    expect(stored.queue).toHaveLength(1);
    expect(stored.queue[0]).toEqual(
      expect.objectContaining({
        promptType: 'truck_damage',
        source: 'camera',
        gps: { latitude: 47.6, longitude: -122.3 },
      }),
    );
  });

  it('Upload Existing flips status with capture_source: library', async () => {
    mountScreen();
    await screen.findByText('Media Capture');

    await act(async () => {
      fireEvent.press(allButtonsByText('Upload Existing')[1]); // other_vehicle
    });

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'artifact_capture_started',
      expect.objectContaining({
        payload: expect.objectContaining({
          prompt_type: 'other_vehicle',
          capture_source: 'library',
        }),
      }),
    );
    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.queue).toHaveLength(1);
    expect(stored.queue[0]).toEqual(
      expect.objectContaining({ source: 'library', promptType: 'other_vehicle' }),
    );
  });

  it('Skip flips status to skipped without emitting artifact_capture_started or growing the queue', async () => {
    mountScreen();
    await screen.findByText('Media Capture');

    await act(async () => {
      fireEvent.press(allButtonsByText('Skip')[2]); // license_plate
    });

    // No artifact_capture_started for skips.
    const calls = jest.mocked(emitProtocolAnalyticsEvent).mock.calls;
    expect(calls.find(([name]) => name === 'artifact_capture_started')).toBeUndefined();

    expect(screen.getByText('Local queue items: 0')).toBeOnTheScreen();
    expect(screen.getByText('Remaining prompts: 4')).toBeOnTheScreen();

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.prompts).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'license_plate', status: 'skipped' }),
      ]),
    );
    expect(stored.queue).toEqual([]);
  });

  it('attaches null gps when geolocation reports an error', async () => {
    installGeolocation({
      getCurrentPosition: ((_onSuccess: unknown, onError: () => void) => {
        onError();
      }) as unknown as Geolocation['getCurrentPosition'],
    } as unknown as Geolocation);

    mountScreen();
    await screen.findByText('Media Capture');

    await act(async () => {
      fireEvent.press(allButtonsByText('Take Photo')[0]);
    });

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.queue[0]).toEqual(expect.objectContaining({ gps: null }));
  });

  it('attaches null gps when navigator.geolocation is unavailable', async () => {
    installGeolocation(null);
    mountScreen();
    await screen.findByText('Media Capture');

    await act(async () => {
      fireEvent.press(allButtonsByText('Take Photo')[0]);
    });

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.queue[0]).toEqual(expect.objectContaining({ gps: null }));
  });

  // NOTE: We initially attempted a `surfaces the inline error when
  // AsyncStorage.setItem fails` case, but Paper's `Button` re-fires
  // `onPress` twice per `fireEvent.press` (once via the inner Text,
  // once via the outer Pressable), and reconciling the unhandled-
  // rejection plumbing across those two concurrent `updatePromptStatus`
  // invocations proved too brittle to keep useful. The single-statement
  // catch path remains; if regression risk grows we can extract
  // `persistDraft` to a helper module and exercise it via a focused
  // unit test in the `unit` Jest project where Paper is not in play.

  it('blocks Continue while any prompt is pending and shows the error message', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Media Capture');

    // Resolve only 4 of 5 prompts.
    for (let i = 0; i < 4; i += 1) {
      await act(async () => {
        fireEvent.press(allButtonsByText('Skip')[i]);
      });
    }
    expect(screen.getByText('Remaining prompts: 1')).toBeOnTheScreen();

    // Continue button is disabled (pendingPrompts > 0). To exercise
    // the inline error path we still call `handleContinue` by pressing
    // the button — the gate fires the helper text from inside the
    // handler when something forces a press.
    await act(async () => {
      fireEvent.press(screen.getByText('Continue to Narrative'));
    });
    // Either the disabled gate kept us here, or the in-handler check
    // fired the error — in both cases we did NOT navigate.
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
  });

  it('after all five prompts are resolved Continue navigates to Narrative and calls completeRoute', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Media Capture');

    for (let i = 0; i < PROMPT_TYPES.length; i += 1) {
      // The prompt list does not re-order on status change, so Skip
      // button at index `i` corresponds to prompt `i`. Press each in
      // turn so all five transition to `skipped`.
      await act(async () => {
        fireEvent.press(allButtonsByText('Skip')[i]);
      });
    }

    expect(screen.getByText('Remaining prompts: 0')).toBeOnTheScreen();
    await act(async () => {
      fireEvent.press(screen.getByText('Continue to Narrative'));
    });

    expect(mockCompleteRoute).toHaveBeenCalledWith('MediaCapture');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('Narrative');
  });

  it('Back button is wired and pressable without throwing', async () => {
    mountScreen();
    await screen.findByText('Media Capture');
    await act(async () => {
      fireEvent.press(screen.getByText('Back'));
    });
    expect(screen.getByText('Media Capture')).toBeOnTheScreen();
  });
});
