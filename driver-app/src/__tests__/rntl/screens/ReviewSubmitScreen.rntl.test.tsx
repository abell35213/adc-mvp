/**
 * RNTL coverage for `ReviewSubmitScreen`.
 *
 * The screen presents:
 *   - A workflow checklist (one row per route in `PROTOCOL_ROUTE_ORDER`
 *     except `ReviewSubmit` and `IncidentStatus`) showing
 *     Complete/Pending chips driven by `completedRoutes`.
 *   - A submission-readiness card whose upload-status line reflects
 *     `getDriverIncidentStatus(incidentId).capture_state`.
 *   - A "Submit Incident Report" CTA that:
 *       1. blocks while `MINIMUM_SUBMISSION_ROUTES` are not all
 *          complete,
 *       2. blocks when `capture_state === 'failed'`,
 *       3. POSTs `submitDriverIncidentReport`, emits
 *          `driver_report_submitted`, calls `completeRoute`, and
 *          navigates to `IncidentStatus`.
 *   - A "Save and Finish Later" CTA that just `completeRoute` +
 *     navigates to `IncidentStatus` without submitting.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';

import type { ProtocolRouteName } from '../../../navigation/protocolFlow';

const mockCompleteRoute = jest.fn();
let mockCompletedRoutes = new Set<ProtocolRouteName>();

jest.mock('../../../api', () => {
  const actual = jest.requireActual('../../../api');
  return {
    ...actual,
    getDriverActiveIncident: jest.fn(),
    getDriverIncidentStatus: jest.fn(),
    submitDriverIncidentReport: jest.fn(),
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
      completedRoutes: mockCompletedRoutes,
      protocolContext: { workflowCorrelationId: 'wfc-review' },
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
import ReviewSubmitScreen from '../../../screens/ReviewSubmitScreen';
import { renderScreen } from '../test-utils';

const mockedActiveIncident = () => jest.mocked(api.getDriverActiveIncident);
const mockedIncidentStatus = () => jest.mocked(api.getDriverIncidentStatus);
const mockedSubmitReport = () => jest.mocked(api.submitDriverIncidentReport);

const ALL_REQUIRED: ProtocolRouteName[] = [
  'IncidentConfirm',
  'VehicleConfirm',
  'SafetyGate',
  'InstructionStep',
  'SceneFacts',
  'MediaCapture',
  'Narrative',
];

const setCompletedRoutes = (routes: ProtocolRouteName[]) => {
  mockCompletedRoutes = new Set(routes);
};

const mountScreen = () =>
  renderScreen({
    name: 'ReviewSubmit',
    component: ReviewSubmitScreen,
    siblings: [{ name: 'IncidentStatus' }, { name: 'DriverHome' }],
  });

const buildStatus = (
  capture_state: api.DriverIncidentStatusResponse['capture_state'],
): api.DriverIncidentStatusResponse => ({
  incident_id: 'inc-99',
  status: 'evidence_capturing',
  safety_notified: true,
  capture_state,
  last_evidence_update_utc: null,
});

describe('ReviewSubmitScreen', () => {
  beforeEach(() => {
    setCompletedRoutes([]);
    mockedActiveIncident().mockResolvedValue({
      incident_id: 'inc-99',
      status: 'open',
    } as api.DriverActiveIncidentResponse);
    mockedIncidentStatus().mockResolvedValue(buildStatus('completed'));
    mockedSubmitReport().mockResolvedValue({
      incident_id: 'inc-99',
      status: 'submitted',
    } as api.DriverSubmitIncidentReportResponse);
  });

  it('renders one checklist row per reviewable route with Complete/Pending chips', async () => {
    setCompletedRoutes(['IncidentConfirm', 'VehicleConfirm']);
    mountScreen();
    await screen.findByText('Workflow checklist');

    expect(screen.getByText('Incident confirmed')).toBeOnTheScreen();
    expect(screen.getByText('Vehicle confirmed')).toBeOnTheScreen();
    expect(screen.getByText('Safety gate acknowledged')).toBeOnTheScreen();
    expect(screen.getByText('Narrative completed')).toBeOnTheScreen();

    // Two complete + several pending chips.
    expect(screen.getAllByText('Complete').length).toBe(2);
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
  });

  it('omits ReviewSubmit and IncidentStatus rows from the checklist', async () => {
    mountScreen();
    await screen.findByText('Workflow checklist');

    expect(screen.queryByText('Review completed')).toBeNull();
    expect(screen.queryByText('Status reviewed')).toBeNull();
  });

  it('shows "Loading…" then the upload-status label from getDriverIncidentStatus', async () => {
    mockedIncidentStatus().mockReset();
    let resolveStatus: (value: api.DriverIncidentStatusResponse) => void;
    mockedIncidentStatus().mockImplementationOnce(
      () =>
        new Promise<api.DriverIncidentStatusResponse>((resolve) => {
          resolveStatus = resolve;
        }),
    );

    mountScreen();
    await screen.findByText('Submission readiness');
    expect(screen.getByText(/Upload status: Loading…/)).toBeOnTheScreen();

    await act(async () => {
      resolveStatus!(buildStatus('in_progress'));
    });
    expect(await screen.findByText(/Upload status: Uploading\./)).toBeOnTheScreen();
  });

  it('renders "Unknown" upload status when no active incident is available', async () => {
    mockedActiveIncident().mockResolvedValue(null as unknown as api.DriverActiveIncidentResponse);
    mountScreen();
    await screen.findByText('Submission readiness');
    expect(await screen.findByText(/Upload status: Unknown\./)).toBeOnTheScreen();
  });

  it('blocks submission with the minimum-requirements error when any required route is incomplete', async () => {
    setCompletedRoutes(ALL_REQUIRED.filter((route) => route !== 'Narrative'));
    const { getNavigation } = mountScreen();
    await screen.findByText('Submission readiness');

    expect(
      screen.getByText(/Minimum requirements: Pending required components/),
    ).toBeOnTheScreen();

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(
      screen.getByText(
        'Minimum requirements are not complete. Finish required workflow components.',
      ),
    ).toBeOnTheScreen();
    expect(mockedSubmitReport()).not.toHaveBeenCalled();
    expect(mockCompleteRoute).not.toHaveBeenCalled();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('ReviewSubmit');
  });

  it('blocks submission with the retry message when capture_state is failed', async () => {
    setCompletedRoutes(ALL_REQUIRED);
    mockedIncidentStatus()
      .mockResolvedValueOnce(buildStatus('failed'))
      .mockResolvedValueOnce(buildStatus('failed'));
    const { getNavigation } = mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(
      screen.getByText('Uploads failed. Retry media upload before submitting.'),
    ).toBeOnTheScreen();
    expect(mockedSubmitReport()).not.toHaveBeenCalled();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('ReviewSubmit');
  });

  it('happy-path submit calls submitDriverIncidentReport, emits analytics, and navigates to IncidentStatus', async () => {
    setCompletedRoutes(ALL_REQUIRED);
    const { getNavigation } = mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(mockedSubmitReport()).toHaveBeenCalledWith('inc-99');
    expect(emitProtocolAnalyticsEvent).toHaveBeenCalledWith(
      'driver_report_submitted',
      expect.objectContaining({
        incidentId: 'inc-99',
        workflowCorrelationId: 'wfc-review',
      }),
    );
    expect(mockCompleteRoute).toHaveBeenCalledWith('ReviewSubmit');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStatus');
  });

  it('surfaces the API error message when submitDriverIncidentReport throws an Error', async () => {
    setCompletedRoutes(ALL_REQUIRED);
    mockedSubmitReport().mockRejectedValueOnce(new Error('server 500'));
    const { getNavigation } = mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(screen.getByText('server 500')).toBeOnTheScreen();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('ReviewSubmit');
  });

  it('surfaces the generic fallback when submitDriverIncidentReport throws a non-Error value', async () => {
    setCompletedRoutes(ALL_REQUIRED);
    mockedSubmitReport().mockImplementationOnce(() => {
      throw 'opaque'; // non-Error throw to exercise the fallback branch
    });
    mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(screen.getByText('Unable to submit incident report.')).toBeOnTheScreen();
  });

  it('surfaces "No active incident" when the lookup returns no incident at submit time', async () => {
    setCompletedRoutes(ALL_REQUIRED);
    // First call (initial upload-status load) returns the incident so the
    // screen renders normally; the second call (submit) returns null.
    mockedActiveIncident()
      .mockResolvedValueOnce({
        incident_id: 'inc-99',
        status: 'open',
      } as api.DriverActiveIncidentResponse)
      .mockResolvedValueOnce(null as unknown as api.DriverActiveIncidentResponse);
    mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Submit Incident Report'));
    });

    expect(screen.getByText('No active incident found to submit.')).toBeOnTheScreen();
    expect(mockedSubmitReport()).not.toHaveBeenCalled();
  });

  it('Save and Finish Later calls completeRoute and navigates to IncidentStatus without submitting', async () => {
    const { getNavigation } = mountScreen();
    await screen.findByText('Submission readiness');

    await act(async () => {
      fireEvent.press(screen.getByText('Save and Finish Later'));
    });

    expect(mockCompleteRoute).toHaveBeenCalledWith('ReviewSubmit');
    expect(mockedSubmitReport()).not.toHaveBeenCalled();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentStatus');
  });

  it('Back button is wired and pressable without throwing', async () => {
    mountScreen();
    await screen.findByText('Submission readiness');
    await act(async () => {
      fireEvent.press(screen.getByText('Back'));
    });
    expect(screen.getByText('Review & Submit')).toBeOnTheScreen();
  });
});
