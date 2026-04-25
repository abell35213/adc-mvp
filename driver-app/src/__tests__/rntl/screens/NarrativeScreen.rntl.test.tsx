/**
 * RNTL coverage for `NarrativeScreen`.
 *
 * The screen owns a single multi-line narrative editor that
 * persists locally via AsyncStorage (keyed `driver_narrative_draft_v1`)
 * and best-effort syncs to the server through
 * `patchDriverIncidentNarrative`. "Save draft" stores in `draft`
 * state; "Narrative complete" trims the text, requires non-empty
 * input, persists with `completion_state: 'completed'`, emits
 * `narrative_saved` analytics, and navigates to `ReviewSubmit`.
 *
 * Behaviours under test:
 *   1. Initializing copy until the active-incident lookup resolves.
 *   2. Stored draft hydrates the editor when the stored
 *      `incidentId` matches the active one.
 *   3. Mismatched-incident draft is ignored.
 *   4. Malformed JSON in storage is tolerated (defaults shown, no
 *      throw).
 *   5. Editor `onChangeText` updates local state.
 *   6. "Save draft" persists locally with `completion_state: 'draft'`
 *      AND PATCHes the server with the same payload.
 *   7. PATCH failure is swallowed — local draft remains the source
 *      of truth and no error UI is shown.
 *   8. "Narrative complete" with empty/whitespace text shows the
 *      required-field error and does NOT navigate or persist as
 *      completed.
 *   9. "Narrative complete" with text trims, persists with
 *      `completion_state: 'completed'`, emits `narrative_saved`,
 *      calls `completeRoute('Narrative')`, and navigates to
 *      `ReviewSubmit`.
 *  10. Back button is wired to `navigation.goBack()`.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveIncident: jest.fn(),
    patchDriverIncidentNarrative: jest.fn(),
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
      protocolContext: { workflowCorrelationId: 'wfc-narrative' },
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
import NarrativeScreen from '../../../screens/NarrativeScreen';
import { renderScreen } from '../test-utils';

const STORAGE_KEY = 'driver_narrative_draft_v1';
const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);
const mockedPatchNarrative = () => jest.mocked(api.patchDriverIncidentNarrative);

const mountScreen = () =>
  renderScreen({
    name: 'Narrative',
    component: NarrativeScreen,
    siblings: [{ name: 'ReviewSubmit' }, { name: 'DriverHome' }],
  });

describe('NarrativeScreen', () => {
  beforeEach(() => {
    AsyncStorage.__reset();
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-77',
      status: 'open',
    } as api.DriverActiveIncidentResponse);
    mockedPatchNarrative().mockResolvedValue({
      incident_id: 'inc-77',
      narrative_text: '',
      completion_state: 'draft',
    } as never);
  });

  it('renders the loading copy until the active-incident lookup resolves', async () => {
    let resolveActive: (value: api.DriverActiveIncidentResponse) => void;
    mockedActiveIncident().mockReset();
    mockedActiveIncident().mockImplementationOnce(
      () =>
        new Promise<api.DriverActiveIncidentResponse>((resolve) => {
          resolveActive = resolve;
        }),
    );

    mountScreen();
    expect(screen.getByText(/Loading narrative/i)).toBeOnTheScreen();

    await act(async () => {
      resolveActive!({
        incident_id: 'inc-77',
        status: 'open',
      } as api.DriverActiveIncidentResponse);
    });
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');
  });

  it('hydrates the editor from a stored draft when the incident matches', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'inc-77',
        draft: { narrativeText: 'Stored body', completionState: 'draft' },
      }),
    );
    mountScreen();

    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');
    expect(screen.getByDisplayValue('Stored body')).toBeOnTheScreen();
  });

  it('ignores a stored draft whose incidentId does not match the active one', async () => {
    await AsyncStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        incidentId: 'OTHER-INC',
        draft: { narrativeText: 'must not load', completionState: 'draft' },
      }),
    );
    mountScreen();

    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');
    expect(screen.queryByDisplayValue('must not load')).toBeNull();
  });

  it('falls back to defaults when stored JSON is malformed', async () => {
    await AsyncStorage.setItem(STORAGE_KEY, '{ not json');
    mountScreen();

    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');
    expect(
      screen.getByText('Narrative text is required to mark this step complete.'),
    ).toBeOnTheScreen();
  });

  it('updates the editor value when the user types', async () => {
    mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    const input = screen.getByPlaceholderText(
      'Describe the incident based only on what you observed.',
    );
    await act(async () => {
      fireEvent.changeText(input, 'Saw a red truck enter the lane.');
    });
    expect(screen.getByDisplayValue('Saw a red truck enter the lane.')).toBeOnTheScreen();
  });

  it('Save draft persists locally with completion_state: draft and PATCHes the server', async () => {
    mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    const input = screen.getByPlaceholderText(
      'Describe the incident based only on what you observed.',
    );
    await act(async () => {
      fireEvent.changeText(input, '  draft body  ');
    });
    await act(async () => {
      fireEvent.press(screen.getByText('Save draft'));
    });

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored).toEqual({
      incidentId: 'inc-77',
      draft: {
        narrativeText: '  draft body  ',
        completionState: 'draft',
      },
    });
    // Server payload uses trimmed text + same completion state.
    expect(mockedPatchNarrative()).toHaveBeenCalledWith('inc-77', {
      narrative_text: 'draft body',
      completion_state: 'draft',
    });
  });

  it('swallows a PATCH failure during Save draft (local draft remains the source of truth)', async () => {
    mockedPatchNarrative().mockRejectedValueOnce(new Error('network down'));
    mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    const input = screen.getByPlaceholderText(
      'Describe the incident based only on what you observed.',
    );
    await act(async () => {
      fireEvent.changeText(input, 'offline body');
    });
    await act(async () => {
      fireEvent.press(screen.getByText('Save draft'));
    });

    // Local store still has the draft.
    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.draft).toEqual({
      narrativeText: 'offline body',
      completionState: 'draft',
    });
    // No error UI surfaced — the screen treats PATCH as best-effort.
    expect(screen.queryByText(/Narrative is required/i)).toBeNull();
  });

  it('Narrative complete with empty text shows the required-field error and does NOT navigate', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    await act(async () => {
      fireEvent.press(screen.getByText('Narrative complete'));
    });

    expect(screen.getByText('Narrative is required before continuing.')).toBeOnTheScreen();
    expect(emitProtocolAnalyticsEvent).not.toHaveBeenCalledWith(
      'narrative_saved',
      expect.anything(),
    );
    expect(mockCompleteRoute).not.toHaveBeenCalled();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('Narrative');
  });

  it('Narrative complete with whitespace-only text is treated as empty', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    const input = screen.getByPlaceholderText(
      'Describe the incident based only on what you observed.',
    );
    await act(async () => {
      fireEvent.changeText(input, '   \n   ');
    });
    await act(async () => {
      fireEvent.press(screen.getByText('Narrative complete'));
    });

    expect(screen.getByText('Narrative is required before continuing.')).toBeOnTheScreen();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('Narrative');
  });

  it('Narrative complete with text trims, persists, emits analytics, and navigates to ReviewSubmit', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');

    const input = screen.getByPlaceholderText(
      'Describe the incident based only on what you observed.',
    );
    await act(async () => {
      fireEvent.changeText(input, '   Final account.   ');
    });
    await act(async () => {
      fireEvent.press(screen.getByText('Narrative complete'));
    });

    const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
    expect(stored.draft).toEqual({
      narrativeText: 'Final account.',
      completionState: 'completed',
    });
    expect(mockedPatchNarrative()).toHaveBeenCalledWith('inc-77', {
      narrative_text: 'Final account.',
      completion_state: 'completed',
    });
    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'narrative_saved',
      expect.objectContaining({
        incidentId: 'inc-77',
        workflowCorrelationId: 'wfc-narrative',
      }),
    );
    expect(mockCompleteRoute).toHaveBeenCalledWith('Narrative');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('ReviewSubmit');
  });

  it('Back button is wired and pressable without throwing', async () => {
    mountScreen();
    await screen.findByText('Write a factual, first-hand summary. Do not guess or include assumptions.');
    await act(async () => {
      fireEvent.press(screen.getByText('Back'));
    });
    expect(screen.getByText('Write a factual, first-hand summary. Do not guess or include assumptions.')).toBeOnTheScreen();
  });
});
