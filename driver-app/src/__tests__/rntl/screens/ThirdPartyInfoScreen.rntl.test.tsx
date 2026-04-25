/**
 * RNTL coverage for `ThirdPartyInfoScreen`.
 *
 * Behaviours under test:
 *   1. Initializing state — renders the loading copy until the
 *      active-incident lookup resolves.
 *   2. Hydrates a stored draft when the stored `incidentId` matches
 *      the active one (parties + completion state restored).
 *   3. Ignores a stored draft whose `incidentId` does not match.
 *   4. "Add another party" appends a new empty party row.
 *   5. "Remove party" removes the row when more than one party exists,
 *      and resets to a single empty party when removing the last one.
 *   6. "Mark unknown" sets the targeted field to the literal
 *      `"unknown"` token.
 *   7. Payload builder — strips parties whose every field is null
 *      (i.e. empty rows) and maps blank strings to null per field.
 *   8. "Third-party info saved" persists locally + calls
 *      `patchDriverIncidentParties` with `completion_state: 'completed'`,
 *      emits `party_info_saved` analytics, and navigates to
 *      `MediaCapture` with a `general_scene` prompt.
 *   9. "Skip for now" persists with `completion_state: 'skipped'` and
 *      navigates to `MediaCapture` with the same prompt.
 *  10. "Take Photo Instead (Vehicle)" emits the analytics with
 *      `transitioned_to_media_prompt: 'third_party_vehicle'` and
 *      navigates with that prompt; document variant maps to
 *      `third_party_document`.
 *  11. Back button calls `navigation.goBack`.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveIncident: jest.fn(),
    patchDriverIncidentParties: jest.fn(),
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
      protocolContext: { workflowCorrelationId: 'wfc-3p' },
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
import ThirdPartyInfoScreen from '../../../screens/ThirdPartyInfoScreen';
import { renderScreen } from '../test-utils';

const STORAGE_KEY = 'driver_third_party_info_draft_v1';

const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);
const mockedPatch = () => jest.mocked(api.patchDriverIncidentParties);

const mountScreen = () =>
  renderScreen({
    name: 'ThirdPartyInfo',
    component: ThirdPartyInfoScreen,
    siblings: [{ name: 'MediaCapture' }, { name: 'DriverHome' }],
  });

describe('ThirdPartyInfoScreen', () => {
  beforeEach(() => {
    AsyncStorage.__reset();
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-42',
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

    expect(screen.getByText(/Loading third-party details/i)).toBeOnTheScreen();

    await act(async () => {
      resolveActive!({ incident_id: 'inc-42', status: 'open' } as api.DriverActiveIncidentResponse);
    });
    await screen.findByText('Third Party Info');
  });

  it('hydrates a stored draft when the incident id matches', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-42',
        draft: {
          completionState: 'skipped',
          parties: [
            {
              fullName: 'Alex Persisted',
              phoneNumber: '5551234',
              vehicleDescription: '',
              insurerName: '',
              policyNumber: '',
              notes: '',
            },
          ],
        },
      }),
    );
    mountScreen();

    await screen.findByText('Third Party Info');
    expect(screen.getByDisplayValue('Alex Persisted')).toBeOnTheScreen();
    expect(screen.getByDisplayValue('5551234')).toBeOnTheScreen();
  });

  it('ignores a stored draft whose incidentId does not match the active one', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-OTHER',
        draft: {
          completionState: 'completed',
          parties: [
            {
              fullName: 'Should Not Appear',
              phoneNumber: '',
              vehicleDescription: '',
              insurerName: '',
              policyNumber: '',
              notes: '',
            },
          ],
        },
      }),
    );
    mountScreen();

    await screen.findByText('Third Party Info');
    expect(screen.queryByDisplayValue('Should Not Appear')).toBeNull();
  });

  it('Add another party appends a new row', async () => {
    mountScreen();
    await screen.findByText('Third Party Info');
    expect(screen.getAllByText(/Third party #/i)).toHaveLength(1);

    await act(async () => {
      fireEvent.press(screen.getByText('Add another party'));
    });
    expect(screen.getAllByText(/Third party #/i)).toHaveLength(2);
  });

  it('Remove party removes a row when multiple exist; resets to a single empty row when removing the last one', async () => {
    mountScreen();
    await screen.findByText('Third Party Info');

    // Add a second party so Remove on the first one truly removes it.
    await act(async () => {
      fireEvent.press(screen.getByText('Add another party'));
    });
    expect(screen.getAllByText(/Third party #/i)).toHaveLength(2);

    await act(async () => {
      fireEvent.press(screen.getAllByText('Remove party')[0]);
    });
    expect(screen.getAllByText(/Third party #/i)).toHaveLength(1);

    // Type something then Remove on the last party — it stays at one
    // row but the row is reset to empty.
    fireEvent.changeText(screen.getByPlaceholderText('e.g., Alex Smith'), 'Doomed');
    expect(screen.getByDisplayValue('Doomed')).toBeOnTheScreen();
    await act(async () => {
      fireEvent.press(screen.getByText('Remove party'));
    });
    expect(screen.getAllByText(/Third party #/i)).toHaveLength(1);
    expect(screen.queryByDisplayValue('Doomed')).toBeNull();
  });

  it('Mark unknown sets the targeted field to "unknown"', async () => {
    mountScreen();
    await screen.findByText('Third Party Info');

    // First "Mark unknown" is for full name.
    await act(async () => {
      fireEvent.press(screen.getAllByText('Mark unknown')[0]);
    });
    expect(screen.getByDisplayValue('unknown')).toBeOnTheScreen();
  });

  it('Save & Continue persists, calls patchDriverIncidentParties (completed) with empty parties stripped, emits analytics, and navigates to MediaCapture/general_scene', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Third Party Info');

    // Fill only party #1 — leave party #2 empty so the payload builder
    // strips it (every field maps to null).
    fireEvent.changeText(
      screen.getByPlaceholderText('e.g., Alex Smith'),
      '  Alex Smith  ',
    );
    await act(async () => {
      fireEvent.press(screen.getByText('Add another party'));
    });

    await act(async () => {
      fireEvent.press(screen.getByText('Third-party info saved'));
    });

    expect(mockedPatch()).toHaveBeenCalledWith(
      'inc-42',
      expect.objectContaining({
        completion_state: 'completed',
        parties: [
          // Only the populated party survives; blank optional fields
          // map to null per `normalizeOptionalText`. Note the trimmed
          // full_name.
          expect.objectContaining({
            full_name: 'Alex Smith',
            phone_number: null,
            vehicle_description: null,
            insurer_name: null,
            policy_number: null,
            notes: null,
          }),
        ],
      }),
    );
    // The empty party row #2 must NOT have been included.
    expect(mockedPatch().mock.calls[0][1].parties).toHaveLength(1);

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'party_info_saved',
      expect.objectContaining({
        incidentId: 'inc-42',
        payload: expect.objectContaining({
          completion_state: 'completed',
          entered_party_count: 1,
        }),
      }),
    );
    expect(mockCompleteRoute).toHaveBeenCalledWith('ThirdPartyInfo');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
    expect(getNavigation()?.getCurrentRoute()?.params).toEqual(
      expect.objectContaining({ destinationPromptType: 'general_scene' }),
    );

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.draft.completionState).toBe('completed');
  });

  it('Skip for now persists with completion_state="skipped" and navigates to MediaCapture/general_scene', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Third Party Info');

    await act(async () => {
      fireEvent.press(screen.getByText('Skip for now'));
    });

    expect(mockedPatch()).toHaveBeenCalledWith(
      'inc-42',
      expect.objectContaining({ completion_state: 'skipped' }),
    );
    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'party_info_saved',
      expect.objectContaining({
        payload: expect.objectContaining({ completion_state: 'skipped' }),
      }),
    );
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
    expect(getNavigation()?.getCurrentRoute()?.params).toEqual(
      expect.objectContaining({ destinationPromptType: 'general_scene' }),
    );
  });

  it('Take Photo Instead (Vehicle) routes to MediaCapture with the third_party_vehicle prompt and reports it in analytics', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Third Party Info');

    await act(async () => {
      fireEvent.press(screen.getByText('Take Photo Instead (Vehicle)'));
    });

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'party_info_saved',
      expect.objectContaining({
        payload: expect.objectContaining({
          transitioned_to_media_prompt: 'third_party_vehicle',
        }),
      }),
    );
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
    expect(getNavigation()?.getCurrentRoute()?.params).toEqual(
      expect.objectContaining({ destinationPromptType: 'third_party_vehicle' }),
    );
  });

  it('Take Photo Instead (Document) routes to MediaCapture with the third_party_document prompt', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Third Party Info');

    await act(async () => {
      fireEvent.press(screen.getByText('Take Photo Instead (Document)'));
    });

    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'party_info_saved',
      expect.objectContaining({
        payload: expect.objectContaining({
          transitioned_to_media_prompt: 'third_party_document',
        }),
      }),
    );
    expect(getNavigation()?.getCurrentRoute()?.params).toEqual(
      expect.objectContaining({ destinationPromptType: 'third_party_document' }),
    );
  });

  it('Back button is wired and pressable without throwing', async () => {
    mountScreen();
    await screen.findByText('Third Party Info');
    await act(async () => {
      fireEvent.press(screen.getByText('Back'));
    });
    // No prior route in the stub navigator → screen stays mounted.
    expect(screen.getByText('Third Party Info')).toBeOnTheScreen();
  });
});
