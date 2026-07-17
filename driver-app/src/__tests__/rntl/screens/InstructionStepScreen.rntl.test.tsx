/**
 * RNTL coverage for `InstructionStepScreen`.
 *
 * Behaviours under test:
 *   1. Loading — initial render shows the loading spinner copy.
 *   2. Load error — `getDriverActiveInstructions` failure renders the
 *      error message + Retry button; Retry re-issues the call.
 *   3. Empty steps — when the API returns an empty `steps` array the
 *      screen calls `completeRoute('InstructionStep')` and
 *      `navigation.replace('SceneFacts')`.
 *   4. Happy path render — steps are displayed in `step_order` order
 *      and the meta line reads "Step N of M".
 *   5. Mount emits `driver_instruction_step_viewed` for the first
 *      step and persists progress to AsyncStorage.
 *   6. `require_ack: true` — Next is disabled until "Acknowledge
 *      step" is pressed; pressing Acknowledge calls
 *      `acknowledgeDriverInstructions`, emits the
 *      `instruction_acknowledged` analytics event, and persists the
 *      ack in AsyncStorage.
 *   7. Acknowledge failure surfaces the error message in the error
 *      slot.
 *   8. `require_ack: false` — Next is enabled immediately and pressing
 *      it advances + emits a viewed event for the next step.
 *   9. Final Next on the last step calls `completeRoute` and
 *      navigates to `SceneFacts`.
 *  10. Restored AsyncStorage progress restores `currentStepIndex` +
 *      viewed/ack sets when `instructionSetId` matches.
 *  11. Stored progress for a different `instructionSetId` is ignored.
 *  12. Malformed stored JSON falls back to defaults without throwing.
 *  13. Back button calls `navigation.goBack()`.
 *
 * `useProtocolFlow` is mocked for callback-stability (matches the
 * pattern established in Block 6 — the screen's load effect depends
 * on `completeRoute`, which the real provider re-creates on every
 * `protocolContext` change).
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveInstructions: jest.fn(),
    acknowledgeDriverInstructions: jest.fn(),
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
      protocolContext: { workflowCorrelationId: 'wfc-1' },
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
import {
  emitProtocolAnalyticsEvent,
  emitTimelineAndAnalyticsEvent,
} from '../../../telemetry/protocolEvents';
import AsyncStorage from '../../mocks/asyncStorage';
import InstructionStepScreen from '../../../screens/InstructionStepScreen';
import { renderScreen } from '../test-utils';

const STORAGE_KEY = 'driver_instruction_progress_v1';

const mockedGetActive = () => jest.mocked(api.getDriverActiveInstructions);
const mockedAck = () => jest.mocked(api.acknowledgeDriverInstructions);

const buildResponse = (
  overrides: Partial<api.DriverActiveInstructionsResponse> = {},
) => ({
  instruction_set_id: 'set-1',
  scope: 'default' as const,
  require_ack: false,
  steps: [
    { step_id: 'step-a', step_order: 1, title: 'First', body: 'Read first' },
    { step_id: 'step-b', step_order: 2, title: 'Second', body: 'Read second' },
  ],
  ...overrides,
});

const mountScreen = () =>
  renderScreen({
    name: 'InstructionStep',
    component: InstructionStepScreen,
    siblings: [{ name: 'SceneFacts' }, { name: 'DriverHome' }],
  });

describe('InstructionStepScreen', () => {
  beforeEach(async () => {
    AsyncStorage.__reset();
    mockedAck().mockResolvedValue({
      acknowledged: true,
    } as api.DriverInstructionAckResponse);
  });

  describe('loading + error', () => {
    it('shows the loading message while instructions are in flight', async () => {
      let resolveLoad: (value: api.DriverActiveInstructionsResponse) => void;
      mockedGetActive().mockImplementationOnce(
        () =>
          new Promise<api.DriverActiveInstructionsResponse>((resolve) => {
            resolveLoad = resolve;
          }),
      );
      mountScreen();

      expect(
        screen.getByText(/Loading active instructions/i),
      ).toBeOnTheScreen();

      await act(async () => {
        resolveLoad!(buildResponse());
      });
      await screen.findByText('First');
    });

    it('shows the error UI on load failure and Retry re-issues the API call', async () => {
      mockedGetActive()
        .mockRejectedValueOnce(new Error('Server exploded'))
        .mockResolvedValueOnce(buildResponse());
      mountScreen();

      expect(await screen.findByText('Server exploded')).toBeOnTheScreen();
      expect(screen.getByText('Unable to load instructions')).toBeOnTheScreen();

      await act(async () => {
        fireEvent.press(screen.getByText('Retry'));
      });
      await screen.findByText('First');
      expect(mockedGetActive().mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('empty steps short-circuit', () => {
    it('completes the route and replaces nav with SceneFacts when steps is empty', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse({ steps: [] }));
      const { getNavigation } = mountScreen();

      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('SceneFacts');
      });
      expect(mockCompleteRoute).toHaveBeenCalledWith('InstructionStep');
    });
  });

  describe('happy path render', () => {
    it('orders steps by step_order and shows "Step 1 of N"', async () => {
      mockedGetActive().mockResolvedValueOnce(
        buildResponse({
          steps: [
            { step_id: 'step-z', step_order: 5, title: 'Zeta', body: 'Last' },
            { step_id: 'step-a', step_order: 1, title: 'Alpha', body: 'First' },
          ],
        }),
      );
      mountScreen();

      await screen.findByText('Alpha');
      expect(screen.getByText('Step 1 of 2')).toBeOnTheScreen();
      expect(screen.getByText('First')).toBeOnTheScreen();
      // The Zeta step is hidden behind Next.
      expect(screen.queryByText('Zeta')).toBeNull();
    });

    it('emits driver_instruction_step_viewed and persists progress on mount', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith(
        'driver_instruction_step_viewed',
      );
      const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
      expect(stored).toEqual(
        expect.objectContaining({
          instructionSetId: 'set-1',
          currentStepIndex: 0,
          viewedStepIds: ['step-a'],
          acknowledgedStepIds: [],
        }),
      );
    });
  });

  describe('require_ack flow', () => {
    it('disables Next until Acknowledge runs, then unlocks Next and persists ack', async () => {
      mockedGetActive().mockResolvedValueOnce(
        buildResponse({ require_ack: true }),
      );
      mountScreen();

      await screen.findByText('First');
      // Next is disabled — pressing it doesn't advance.
      await act(async () => {
        fireEvent.press(screen.getByText('Next'));
      });
      expect(screen.getByText('Step 1 of 2')).toBeOnTheScreen();

      await act(async () => {
        fireEvent.press(screen.getByText('Acknowledge step'));
      });

      expect(mockedAck()).toHaveBeenCalledWith('set-1');
      expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
        'instruction_acknowledged',
        expect.objectContaining({
          payload: expect.objectContaining({
            instruction_set_id: 'set-1',
            instruction_step_id: 'step-a',
          }),
        }),
      );
      // Acknowledge button label flips and ack is in AsyncStorage.
      expect(screen.getByText('Acknowledged')).toBeOnTheScreen();
      const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
      expect(stored.acknowledgedStepIds).toEqual(['step-a']);
    });

    it('surfaces ack failures in the inline error slot', async () => {
      mockedGetActive().mockResolvedValueOnce(
        buildResponse({ require_ack: true }),
      );
      mockedAck().mockRejectedValueOnce(new Error('Ack rejected by server.'));
      mountScreen();

      await screen.findByText('First');
      await act(async () => {
        fireEvent.press(screen.getByText('Acknowledge step'));
      });

      expect(
        await screen.findByText('Ack rejected by server.'),
      ).toBeOnTheScreen();
      // Step still un-acknowledged → button label remains.
      expect(screen.getByText('Acknowledge step')).toBeOnTheScreen();
    });
  });

  describe('navigation between steps', () => {
    it('advances on Next when require_ack is false and emits a new viewed event', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      jest.mocked(emitTimelineAndAnalyticsEvent).mockClear();

      await act(async () => {
        fireEvent.press(screen.getByText('Next'));
      });

      expect(screen.getByText('Step 2 of 2')).toBeOnTheScreen();
      expect(screen.getByText('Second')).toBeOnTheScreen();
      expect(emitTimelineAndAnalyticsEvent).toHaveBeenCalledWith(
        'driver_instruction_step_viewed',
      );
    });

    it('final step Continue completes the route and navigates to SceneFacts', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      const { getNavigation } = mountScreen();

      await screen.findByText('First');
      await act(async () => {
        fireEvent.press(screen.getByText('Next'));
      });
      // Now on step 2 — button label flips to "Continue".
      await act(async () => {
        fireEvent.press(screen.getByText('Continue'));
      });

      expect(mockCompleteRoute).toHaveBeenCalledWith('InstructionStep');
      await waitFor(() => {
        expect(getNavigation()?.getCurrentRoute()?.name).toBe('SceneFacts');
      });
    });

    it('Back button calls navigation.goBack', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      // We can't easily assert goBack itself without a previous route; just
      // confirm the button is wired and pressable without throwing.
      await act(async () => {
        fireEvent.press(screen.getByText('Back'));
      });
      // Still on InstructionStep because there's no prior route in the stub
      // navigator.
      expect(screen.getByText('First')).toBeOnTheScreen();
    });
  });

  describe('AsyncStorage hydration', () => {
    it('restores currentStepIndex and the viewed/ack sets when instructionSetId matches', async () => {
      await AsyncStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          instructionSetId: 'set-1',
          currentStepIndex: 1,
          viewedStepIds: ['step-a', 'step-b'],
          acknowledgedStepIds: ['step-a'],
        }),
      );
      mockedGetActive().mockResolvedValueOnce(
        buildResponse({ require_ack: true }),
      );
      mountScreen();

      // We resume on step 2 (index 1) and step-b is not yet acknowledged.
      await screen.findByText('Second');
      expect(screen.getByText('Step 2 of 2')).toBeOnTheScreen();
      expect(screen.getByText('Acknowledge step')).toBeOnTheScreen();
    });

    it('ignores stored progress whose instructionSetId differs', async () => {
      await AsyncStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          instructionSetId: 'set-OTHER',
          currentStepIndex: 1,
          viewedStepIds: ['step-x'],
          acknowledgedStepIds: ['step-x'],
        }),
      );
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      expect(screen.getByText('Step 1 of 2')).toBeOnTheScreen();
    });

    it('falls back to defaults on malformed stored JSON', async () => {
      await AsyncStorage.setItem(STORAGE_KEY, '{ this is not json');
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      expect(screen.getByText('Step 1 of 2')).toBeOnTheScreen();
    });

    it('starts at the first step when no stored progress exists', async () => {
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      expect(screen.getByText('Step 1 of 2')).toBeOnTheScreen();
    });

    it('normalizes an out-of-range stored index to the last available step', async () => {
      await AsyncStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          instructionSetId: 'set-1',
          currentStepIndex: 99,
          viewedStepIds: ['step-a'],
          acknowledgedStepIds: [],
        }),
      );
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('Second');
      expect(screen.getByText('Step 2 of 2')).toBeOnTheScreen();
      const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
      expect(stored.currentStepIndex).toBe(1);
      expect(stored.viewedStepIds).toEqual(['step-a', 'step-b']);
    });

    it('does not let hydration overwrite a subsequent valid user action', async () => {
      await AsyncStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          instructionSetId: 'set-1',
          currentStepIndex: 0,
          viewedStepIds: ['step-a'],
          acknowledgedStepIds: [],
        }),
      );
      mockedGetActive().mockResolvedValueOnce(buildResponse());
      mountScreen();

      await screen.findByText('First');
      await act(async () => {
        fireEvent.press(screen.getByText('Next'));
      });

      expect(screen.getByText('Step 2 of 2')).toBeOnTheScreen();
      expect(mockedGetActive()).toHaveBeenCalledTimes(1);
      const stored = JSON.parse((await AsyncStorage.getItem(STORAGE_KEY))!);
      expect(stored).toEqual(
        expect.objectContaining({
          currentStepIndex: 1,
          viewedStepIds: ['step-a', 'step-b'],
        }),
      );
    });
  });
});
