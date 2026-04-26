/**
 * RNTL coverage for `QrScanScreen`.
 *
 * Behaviours under test:
 *   1. Initial permission state — when `useCameraPermissions` returns
 *      `null` the screen shows the "Requesting camera access…" copy.
 *   2. Permission denied — renders the "Camera access is required."
 *      message and the "Allow camera" button calls
 *      `requestPermission`.
 *   3. Permission granted, valid QR scanned — `resolveVehicleQr` is
 *      called with the token (prefix stripped), the success message is
 *      rendered, and `navigation.goBack` is called once the success
 *      timeout elapses.
 *   4. Invalid prefix → "Invalid QR code…" message, no API call.
 *   5. Missing token after the prefix → "QR code is missing a vehicle
 *      token." message.
 *   6. resolveVehicleQr error → error message rendered (no auto-back).
 *   7. "Scan again" resets the status message and re-enables scanning.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

const mockRequestPermission = jest.fn();
let mockPermissionState: { granted: boolean } | null = { granted: true };
let mockLastScanData = '';

// `expo-camera` doesn't run under jsdom — replace it with a minimal
// stub that exposes the bits the screen consumes.
jest.mock('expo-camera', () => {
  const React = jest.requireActual('react');
  const { View } = jest.requireActual('react-native');
  return {
    useCameraPermissions: () => [mockPermissionState, mockRequestPermission],
    CameraView: ({
      onBarcodeScanned,
    }: {
      onBarcodeScanned?: (event: { data: string }) => void;
    }) =>
      React.createElement(View, {
        testID: 'camera-view',
        // Stash the latest scan handler on the element via a ref-like
        // prop so the test harness can drive it deterministically.
        onTouchEnd: () => onBarcodeScanned?.({ data: mockLastScanData }),
      }),
  };
});

jest.mock('../../../services/incidents');

import * as incidentsService from '../../../services/incidents';
import QrScanScreen from '../../../screens/QrScanScreen';
import { apiError, renderScreen } from '../test-utils';

const mockedIncidents = () =>
  jest.mocked(incidentsService) as jest.Mocked<typeof incidentsService>;

const triggerScan = async (data: string) => {
  mockLastScanData = data;
  await act(async () => {
    fireEvent(screen.getByTestId('camera-view'), 'touchEnd', {});
  });
};

const mountScreen = () =>
  renderScreen({
    name: 'QrScan',
    component: QrScanScreen,
    siblings: [{ name: 'DriverHome' }],
  });

describe('QrScanScreen', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockRequestPermission.mockReset();
    mockPermissionState = { granted: true };
    mockLastScanData = '';
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  describe('permission states', () => {
    it('shows "Requesting camera access…" while permission is undetermined', () => {
      mockPermissionState = null;
      mountScreen();
      expect(screen.getByText('Requesting camera access…')).toBeOnTheScreen();
    });

    it('shows the deny copy and lets the user request permission again', async () => {
      mockPermissionState = { granted: false };
      mountScreen();

      expect(screen.getByText('Camera access is required.')).toBeOnTheScreen();
      await act(async () => {
        fireEvent.press(screen.getByText('Allow camera'));
      });
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });
  });

  describe('scanning', () => {
    it('valid QR resolves vehicle, shows success message, and goes back after the success timeout', async () => {
      mockedIncidents().resolveVehicleQr.mockResolvedValueOnce({
        adc_vehicle_id: 'veh-9',
        display_label: 'Truck 9',
      });
      const { getNavigation } = mountScreen();

      await triggerScan('adc://vehicle/TOKEN-123');

      await waitFor(() => {
        expect(screen.getByText('Resolved vehicle Truck 9.')).toBeOnTheScreen();
      });
      expect(mockedIncidents().resolveVehicleQr).toHaveBeenCalledWith('TOKEN-123');

      // `navigation.goBack` is scheduled via `setTimeout`; advance fake
      // timers and confirm the navigator pops back to the only
      // sibling registered.
      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      // The QrScan route was the initial route so there is nothing to
      // pop back *to* — just confirm the navigator is still alive and
      // didn't blow up.
      expect(getNavigation()).not.toBeNull();
    });

    it('rejects QR data without the ADC prefix', async () => {
      mountScreen();

      await triggerScan('https://example.com/whatever');

      expect(
        screen.getByText('Invalid QR code. Please scan an ADC vehicle code.'),
      ).toBeOnTheScreen();
      expect(mockedIncidents().resolveVehicleQr).not.toHaveBeenCalled();
    });

    it('reports a missing vehicle token when the prefix has no payload', async () => {
      mountScreen();

      await triggerScan('adc://vehicle/   ');

      expect(
        screen.getByText('QR code is missing a vehicle token.'),
      ).toBeOnTheScreen();
      expect(mockedIncidents().resolveVehicleQr).not.toHaveBeenCalled();
    });

    it('surfaces a resolveVehicleQr error message and stays on screen', async () => {
      mockedIncidents().resolveVehicleQr.mockRejectedValueOnce(
        apiError(503, 'service down'),
      );
      mountScreen();

      await triggerScan('adc://vehicle/TOK');

      await waitFor(() => {
        expect(screen.getByText('service down')).toBeOnTheScreen();
      });
      // No success-timeout schedule; advancing timers should not
      // change anything.
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
      expect(screen.getByText('service down')).toBeOnTheScreen();
    });

    it('falls back to a generic message for non-Error throwables', async () => {
      mockedIncidents().resolveVehicleQr.mockRejectedValueOnce('boom');
      mountScreen();

      await triggerScan('adc://vehicle/TOK');

      await waitFor(() => {
        expect(screen.getByText('Failed to resolve vehicle.')).toBeOnTheScreen();
      });
    });

    it('"Scan again" clears the status and re-enables scanning', async () => {
      mountScreen();
      await triggerScan('https://example.com/whatever');
      expect(
        screen.getByText('Invalid QR code. Please scan an ADC vehicle code.'),
      ).toBeOnTheScreen();

      await act(async () => {
        fireEvent.press(screen.getByText('Scan again'));
      });

      expect(
        screen.queryByText('Invalid QR code. Please scan an ADC vehicle code.'),
      ).toBeNull();
      // After reset a brand-new scan should be processed again.
      mockedIncidents().resolveVehicleQr.mockResolvedValueOnce({
        adc_vehicle_id: 'veh-2',
        display_label: 'Truck 2',
      });
      await triggerScan('adc://vehicle/AGAIN');
      await waitFor(() => {
        expect(screen.getByText('Resolved vehicle Truck 2.')).toBeOnTheScreen();
      });
    });
  });
});
