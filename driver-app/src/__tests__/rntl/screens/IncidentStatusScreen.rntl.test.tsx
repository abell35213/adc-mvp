/**
 * RNTL coverage for `IncidentStatusScreen`.
 *
 * The screen loads the active incident's status on focus
 * (`useFocusEffect`), surfaces metadata + safety/capture chips, derives
 * an artifact summary and pending-items list from `capture_state` /
 * `safety_notified` / `status`, and exposes navigation/action CTAs.
 *
 * Behaviours under test:
 *   1. On mount, calls `getDriverActiveIncident` then
 *      `getDriverIncidentStatus(incident_id)` and renders the metadata
 *      + chips.
 *   2. When `getDriverActiveIncident` returns no incident, renders
 *      "Not available" / "Unknown" placeholders and the
 *      "Unable to determine incident status." pending item.
 *   3. API errors surface via the inline `HelperText` using the
 *      Error message.
 *   4. Non-Error throws fall back to the generic copy
 *      ("Unable to load incident status.").
 *   5. Artifact summary mapping: `capture_state === 'completed'` →
 *      uploaded=1; `capture_state === 'failed'` → failed=1; otherwise
 *      pending=1.
 *   6. Pending items reflect `safety_notified`, `capture_state`, and
 *      `status` — and collapse to "No pending items." when fully
 *      closed.
 *   7. "Add More Photos" navigates to `MediaCapture`.
 *   8. "Update Details" navigates to `SceneFacts`.
 *   9. "Call Safety" calls `Linking.openURL('tel:+18005551212')`.
 *  10. "Return to home" calls `completeRoute('IncidentStatus')`,
 *      `resetProtocol()`, and resets navigation to `DriverHome`.
 */

import { Linking } from 'react-native';
import { act, fireEvent, screen } from '@testing-library/react-native';

const mockCompleteRoute = jest.fn();
const mockResetProtocol = jest.fn();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveIncident: jest.fn(),
    getDriverIncidentStatus: jest.fn(),
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
      resetProtocol: mockResetProtocol,
    }),
  };
});

import * as api from '../../../api';
import IncidentStatusScreen from '../../../screens/IncidentStatusScreen';
import { renderScreen } from '../test-utils';

const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);
const mockedIncidentStatus = () => jest.mocked(api.getDriverIncidentStatus);

const buildStatus = (
  overrides: Partial<api.DriverIncidentStatusResponse> = {},
): api.DriverIncidentStatusResponse => ({
  incident_id: 'inc-42',
  status: 'evidence_capturing',
  safety_notified: false,
  capture_state: 'in_progress',
  last_evidence_update_utc: '2026-04-25T16:00:00Z',
  ...overrides,
});

const mountScreen = () =>
  renderScreen({
    name: 'IncidentStatus',
    component: IncidentStatusScreen,
    siblings: [
      { name: 'MediaCapture' },
      { name: 'SceneFacts' },
      { name: 'DriverHome' },
    ],
  });

describe('IncidentStatusScreen', () => {
  beforeEach(() => {
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-42',
      status: 'open',
    } as api.DriverActiveIncidentResponse);
    mockedIncidentStatus().mockResolvedValue(buildStatus());
    jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('loads metadata and chips from getDriverIncidentStatus on mount', async () => {
    mountScreen();

    expect(await screen.findByText('Incident ID: inc-42')).toBeOnTheScreen();
    expect(screen.getByText('Status: evidence_capturing')).toBeOnTheScreen();
    expect(
      screen.getByText('Last evidence update: 2026-04-25T16:00:00Z'),
    ).toBeOnTheScreen();
    expect(screen.getByText('Safety notified: No')).toBeOnTheScreen();
    expect(screen.getByText('Capture: in_progress')).toBeOnTheScreen();
    expect(mockedIncidentStatus()).toHaveBeenCalledWith('inc-42');
  });

  it('renders placeholders and the "Unable to determine" pending item when there is no active incident', async () => {
    mockedActiveIncident().mockResolvedValue(
      null as unknown as api.DriverActiveIncidentResponse,
    );
    mountScreen();

    expect(await screen.findByText('Incident ID: Not available')).toBeOnTheScreen();
    expect(screen.getByText('Status: Unknown')).toBeOnTheScreen();
    expect(screen.getByText('Last evidence update: Not available')).toBeOnTheScreen();
    expect(screen.getByText('• Unable to determine incident status.')).toBeOnTheScreen();
    // Status was never queried because there was no incident_id.
    expect(mockedIncidentStatus()).not.toHaveBeenCalled();
  });

  it('surfaces an Error message via HelperText when status loading fails', async () => {
    mockedIncidentStatus().mockRejectedValueOnce(new Error('upstream timed out'));
    mountScreen();

    expect(await screen.findByText('upstream timed out')).toBeOnTheScreen();
  });

  it('falls back to the generic copy when the failure value is not an Error', async () => {
    mockedIncidentStatus().mockImplementationOnce(() => {
      throw 'opaque';
    });
    mountScreen();

    expect(await screen.findByText('Unable to load incident status.')).toBeOnTheScreen();
  });

  it('artifact summary maps completed → uploaded=1', async () => {
    mockedIncidentStatus().mockResolvedValue(
      buildStatus({ capture_state: 'completed', safety_notified: true, status: 'closed' }),
    );
    mountScreen();

    expect(await screen.findByText('Uploaded: 1')).toBeOnTheScreen();
    expect(screen.getByText('Pending: 0')).toBeOnTheScreen();
    expect(screen.getByText('Failed: 0')).toBeOnTheScreen();
    // All three pending conditions cleared → fallback row.
    expect(screen.getByText('• No pending items.')).toBeOnTheScreen();
  });

  it('artifact summary maps failed → failed=1', async () => {
    mockedIncidentStatus().mockResolvedValue(buildStatus({ capture_state: 'failed' }));
    mountScreen();

    expect(await screen.findByText('Failed: 1')).toBeOnTheScreen();
    expect(screen.getByText('Uploaded: 0')).toBeOnTheScreen();
    expect(screen.getByText('Pending: 0')).toBeOnTheScreen();
  });

  it('artifact summary maps any non-terminal capture state → pending=1', async () => {
    mockedIncidentStatus().mockResolvedValue(buildStatus({ capture_state: 'pending' }));
    mountScreen();

    expect(await screen.findByText('Pending: 1')).toBeOnTheScreen();
    expect(screen.getByText('Uploaded: 0')).toBeOnTheScreen();
    expect(screen.getByText('Failed: 0')).toBeOnTheScreen();
  });

  it('pending items reflect safety_notified, capture_state, and status', async () => {
    // Default `buildStatus` has safety_notified=false, capture_state='in_progress',
    // status='evidence_capturing' → all three pending rows should appear.
    mountScreen();

    expect(await screen.findByText('• Notify safety manager.')).toBeOnTheScreen();
    expect(
      screen.getByText('• Continue evidence upload and verification.'),
    ).toBeOnTheScreen();
    expect(
      screen.getByText('• Review incident details before final closure.'),
    ).toBeOnTheScreen();
  });

  it('"Add More Photos" navigates to MediaCapture', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Incident ID: inc-42');

    await act(async () => {
      fireEvent.press(screen.getByText('Add More Photos'));
    });

    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
  });

  it('"Update Details" navigates to SceneFacts', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Incident ID: inc-42');

    await act(async () => {
      fireEvent.press(screen.getByText('Update Details'));
    });

    expect(getNavigation()?.getCurrentRoute()?.name).toBe('SceneFacts');
  });

  it('"Call Safety" opens the tel: URL for the safety manager', async () => {
    mountScreen();
    await screen.findByText('Incident ID: inc-42');

    await act(async () => {
      fireEvent.press(screen.getByText('Call Safety'));
    });

    expect(Linking.openURL).toHaveBeenCalledWith('tel:+18005551212');
  });

  it('"Return to home" completes the route, resets the protocol, and resets navigation to DriverHome', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Incident ID: inc-42');

    await act(async () => {
      fireEvent.press(screen.getByText('Return to home'));
    });

    expect(mockCompleteRoute).toHaveBeenCalledWith('IncidentStatus');
    expect(mockResetProtocol).toHaveBeenCalledTimes(1);
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
  });
});
