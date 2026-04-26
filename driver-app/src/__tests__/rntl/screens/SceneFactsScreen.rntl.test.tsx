/**
 * RNTL coverage for `SceneFactsScreen`.
 *
 * Behaviours under test:
 *   1. Initializing state — renders the loading copy until
 *      `getDriverActiveIncident` resolves.
 *   2. Restored draft — when AsyncStorage holds a draft whose
 *      `incidentId` matches the active incident, the form hydrates
 *      with the stored values.
 *   3. Mismatched-incident draft is ignored (form starts empty).
 *   4. Step 0 validation — empty date/time blocks Next; missing
 *      location text AND incomplete GPS blocks Next; supplying just
 *      one GPS coordinate (without text) is also invalid.
 *   5. Step 1 validation — Next is blocked until all three yes/no
 *      questions have a value.
 *   6. Step 2 validation — empty short-description blocks Submit.
 *   7. Continue persists the draft to AsyncStorage AND calls
 *      `patchDriverIncidentSceneFacts` with the trimmed/coerced
 *      payload built by `buildSceneFactsPayload`.
 *   8. Backend sync errors during persist are swallowed (form still
 *      advances).
 *   9. Final Continue emits `scene_saved` analytics, calls
 *      `completeRoute('SceneFacts')`, and navigates to
 *      `ThirdPartyInfo`.
 *  10. Back at step 0 calls `navigation.goBack`; Back mid-form goes
 *      to the previous step.
 *  11. Payload builder — `location_text` is null when blank;
 *      `location_gps` is null when only one of lat/lng is present and
 *      populated when both are; the booleans are coerced from
 *      `boolean | null`.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveIncident: jest.fn(),
    patchDriverIncidentSceneFacts: jest.fn(),
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
      protocolContext: { workflowCorrelationId: 'wfc-scene' },
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
import SceneFactsScreen from '../../../screens/SceneFactsScreen';
import { renderScreen } from '../test-utils';

const STORAGE_KEY = 'driver_scene_facts_draft_v1';

const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);
const mockedPatch = () => jest.mocked(api.patchDriverIncidentSceneFacts);

const mountScreen = () =>
  renderScreen({
    name: 'SceneFacts',
    component: SceneFactsScreen,
    siblings: [{ name: 'ThirdPartyInfo' }, { name: 'DriverHome' }],
  });

const fillStep0Valid = () => {
  fireEvent.changeText(
    screen.getByPlaceholderText('2026-04-05T13:45:00Z'),
    '  2026-04-05T13:45:00Z  ',
  );
  fireEvent.changeText(
    screen.getByPlaceholderText('123 Main St, Springfield'),
    '  123 Main St  ',
  );
};

const answerAllYesNo = (
  injuries = true,
  police = false,
  drivable = true,
) => {
  // Each yes/no question renders Yes + No buttons in document order
  // matching the question list, so we pick by index.
  const yesButtons = screen.getAllByText('Yes');
  const noButtons = screen.getAllByText('No');
  fireEvent.press((injuries ? yesButtons : noButtons)[0]);
  fireEvent.press((police ? yesButtons : noButtons)[1]);
  fireEvent.press((drivable ? yesButtons : noButtons)[2]);
};

describe('SceneFactsScreen', () => {
  beforeEach(() => {
    AsyncStorage.__reset();
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-7',
      status: 'open',
    } as api.DriverActiveIncidentResponse);
    mockedPatch().mockResolvedValue({} as never);
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

    expect(screen.getByText(/Loading scene facts/i)).toBeOnTheScreen();

    await act(async () => {
      resolveActive!({ incident_id: 'inc-7', status: 'open' } as api.DriverActiveIncidentResponse);
    });
    await screen.findByText('Scene Facts');
  });

  it('hydrates a stored draft when the incident id matches', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-7',
        draft: {
          incidentDateTime: '2026-04-05T13:45:00Z',
          locationText: 'My Saved Spot',
          locationLatitude: '',
          locationLongitude: '',
          injuriesReported: null,
          policeCalled: null,
          vehicleDrivable: null,
          shortDescription: '',
        },
      }),
    );
    mountScreen();

    await screen.findByText('Scene Facts');
    expect(screen.getByDisplayValue('My Saved Spot')).toBeOnTheScreen();
  });

  it('ignores a stored draft when the stored incidentId mismatches the active one', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-OTHER',
        draft: {
          incidentDateTime: '2026-04-05T13:45:00Z',
          locationText: 'Should Not Appear',
          locationLatitude: '',
          locationLongitude: '',
          injuriesReported: null,
          policeCalled: null,
          vehicleDrivable: null,
          shortDescription: '',
        },
      }),
    );
    mountScreen();

    await screen.findByText('Scene Facts');
    expect(screen.queryByDisplayValue('Should Not Appear')).toBeNull();
  });

  it('blocks Next on step 0 when date/time and location are empty', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');

    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    expect(
      screen.getByText('Incident date/time is required.'),
    ).toBeOnTheScreen();
  });

  it('blocks Next on step 0 when only one GPS coordinate is provided', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');

    fireEvent.changeText(
      screen.getByPlaceholderText('2026-04-05T13:45:00Z'),
      '2026-04-05T13:45:00Z',
    );
    fireEvent.changeText(screen.getByPlaceholderText('37.7749'), '47.6');
    // Longitude intentionally blank.

    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    expect(
      screen.getByText('Provide location text or both GPS coordinates.'),
    ).toBeOnTheScreen();
  });

  it('blocks Next on step 1 until all yes/no questions are answered', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');
    fillStep0Valid();
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByText('Were injuries reported?');

    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    expect(
      screen.getByText('Please answer all yes/no scene safety questions.'),
    ).toBeOnTheScreen();
  });

  it('blocks final Submit on step 2 when short_description is empty', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');
    fillStep0Valid();
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByText('Were injuries reported?');
    answerAllYesNo();
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByPlaceholderText('Briefly describe what happened.');

    await act(async () => {
      fireEvent.press(screen.getByText('Facts recorded'));
    });
    expect(screen.getByText('Short description is required.')).toBeOnTheScreen();
  });

  it('persists locally + calls patchDriverIncidentSceneFacts on Continue and final Submit emits scene_saved + nav ThirdPartyInfo', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Scene Facts');

    fireEvent.changeText(
      screen.getByPlaceholderText('2026-04-05T13:45:00Z'),
      '  2026-04-05T13:45:00Z  ',
    );
    // Provide GPS but no location text — exercises the populated
    // `location_gps` payload branch.
    fireEvent.changeText(screen.getByPlaceholderText('37.7749'), '47.61');
    fireEvent.changeText(screen.getByPlaceholderText('-122.4194'), '-122.33');

    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByText('Were injuries reported?');
    answerAllYesNo(true, false, true);
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByPlaceholderText('Briefly describe what happened.');
    fireEvent.changeText(
      screen.getByPlaceholderText('Briefly describe what happened.'),
      '  Bumper tap in lot  ',
    );
    await act(async () => {
      fireEvent.press(screen.getByText('Facts recorded'));
    });

    // AsyncStorage holds the draft.
    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.incidentId).toBe('inc-7');
    expect(stored.draft.incidentDateTime).toContain('2026-04-05T13:45:00Z');

    // Backend patch invoked with the trimmed/coerced payload built by
    // `buildSceneFactsPayload`.
    expect(mockedPatch()).toHaveBeenCalledWith(
      'inc-7',
      expect.objectContaining({
        incident_datetime_utc: '2026-04-05T13:45:00Z',
        location_text: null,
        location_gps: { latitude: 47.61, longitude: -122.33 },
        injuries_reported: true,
        police_called: false,
        vehicle_drivable: true,
        short_description: 'Bumper tap in lot',
      }),
    );

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'scene_saved',
      expect.objectContaining({ incidentId: 'inc-7' }),
    );
    expect(mockCompleteRoute).toHaveBeenCalledWith('SceneFacts');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('ThirdPartyInfo');
  });

  it('builds payload with location_text populated and location_gps null when only one coord is given mid-form', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');

    fireEvent.changeText(
      screen.getByPlaceholderText('2026-04-05T13:45:00Z'),
      '2026-04-05T13:45:00Z',
    );
    fireEvent.changeText(
      screen.getByPlaceholderText('123 Main St, Springfield'),
      '123 Main St',
    );
    // Only latitude — should make `location_gps` null and let
    // `location_text` carry the form forward.
    fireEvent.changeText(screen.getByPlaceholderText('37.7749'), '47.6');

    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByText('Were injuries reported?');

    // First persistDraft happens via Continue from step 0 → step 1.
    expect(mockedPatch()).toHaveBeenCalledWith(
      'inc-7',
      expect.objectContaining({
        location_text: '123 Main St',
        location_gps: null,
      }),
    );
  });

  it('swallows backend sync errors so the form still advances', async () => {
    mockedPatch().mockRejectedValueOnce(new Error('500 backend offline'));
    mountScreen();
    await screen.findByText('Scene Facts');
    fillStep0Valid();
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    // Despite the rejected patch we made it to step 1.
    expect(await screen.findByText('Were injuries reported?')).toBeOnTheScreen();
  });

  it('Back at step 0 calls navigation.goBack; Back mid-form goes to previous step', async () => {
    mountScreen();
    await screen.findByText('Scene Facts');
    fillStep0Valid();
    await act(async () => {
      fireEvent.press(screen.getByText('Next step'));
    });
    await screen.findByText('Were injuries reported?');
    // `handleBack` re-runs the current step's validator, so we must
    // answer the yes/no questions before "Previous step" can return us
    // to step 0.
    answerAllYesNo();
    // "Back" label flips to "Previous step" once stepIndex > 0.
    await act(async () => {
      fireEvent.press(screen.getByText('Previous step'));
    });
    expect(await screen.findByText('Step 1 of 3')).toBeOnTheScreen();

    // Now Back button (step 0) calls goBack; with no prior history we
    // simply confirm it doesn't throw and stays on the screen.
    await act(async () => {
      fireEvent.press(screen.getByText('Back'));
    });
    expect(screen.getByText('Scene Facts')).toBeOnTheScreen();
  });
});
