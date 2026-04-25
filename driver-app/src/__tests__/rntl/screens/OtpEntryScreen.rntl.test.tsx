/**
 * RNTL coverage for `OtpEntryScreen`.
 *
 * Behaviours under test:
 *   1. Empty-input guard — pressing "Verify & Continue" without typing
 *      surfaces a validation message and never calls the API.
 *   2. Happy path — `verifyOtp` is called with the route's `phoneE164`
 *      and the trimmed code, the returned token is persisted via
 *      `setStoredToken`, and `navigation.reset` lands on `DriverHome`.
 *   3. Renders the route's phone number in the subtitle copy.
 *   4. Snapshot — guards against accidental layout regressions.
 *   5. API error matrix — one assertion per realistic HTTP status code +
 *      generic Error fallback.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { TextInput as RNTextInput } from 'react-native';

jest.mock('../../../api');
import * as api from '../../../api';

import OtpEntryScreen from '../../../screens/OtpEntryScreen';
import { getStoredToken } from '../../../auth';
import { __reset as resetSecureStore } from '../../mocks/secureStore';
import {
  apiError,
  mockedApi,
  renderScreen,
} from '../test-utils';

const PHONE = '+15551234567';
const getInput = () => screen.UNSAFE_getByType(RNTextInput);

describe('OtpEntryScreen', () => {
  beforeEach(() => {
    resetSecureStore();
  });

  const mountScreen = () =>
    renderScreen({
      name: 'OtpEntry',
      component: OtpEntryScreen,
      params: { phoneE164: PHONE },
      siblings: [{ name: 'DriverHome' }, { name: 'PhoneEntry' }],
    });

  it('renders the destination phone number in the subtitle', () => {
    mountScreen();
    expect(screen.getByText(`We sent a code to ${PHONE}.`)).toBeOnTheScreen();
  });

  it('shows a validation error and skips the API call when the field is empty', async () => {
    mountScreen();

    fireEvent.press(screen.getByText('Verify & Continue'));

    expect(await screen.findByText('Enter the code we sent you.')).toBeOnTheScreen();
    expect(mockedApi(api).verifyOtp).not.toHaveBeenCalled();
  });

  it('verifies the OTP, stores the token, and resets navigation to DriverHome', async () => {
    mockedApi(api).verifyOtp.mockResolvedValueOnce({ access_token: 'jwt-abc-123' });

    const { getNavigation } = mountScreen();
    fireEvent.changeText(getInput(), '  654321  ');
    await act(async () => {
      fireEvent.press(screen.getByText('Verify & Continue'));
    });

    await waitFor(() => {
      expect(mockedApi(api).verifyOtp).toHaveBeenCalledWith(PHONE, '654321');
    });
    await waitFor(async () => {
      expect(await getStoredToken()).toBe('jwt-abc-123');
    });
    await waitFor(() => {
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
    });
    // `navigation.reset` clears history so the back stack is single-entry.
    const state = getNavigation()?.getRootState();
    expect(state?.routes).toHaveLength(1);
    expect(state?.index).toBe(0);
  });

  it('matches the rendered snapshot', () => {
    const { screen: rendered } = mountScreen();
    expect(rendered.toJSON()).toMatchSnapshot();
  });

  describe.each([
    [400, 'invalid code'],
    [401, 'wrong code'],
    [410, 'code expired'],
    [422, 'malformed code'],
    [429, 'too many attempts'],
    [500, 'verification service down'],
  ])('surfaces ApiRequestError responses', (status, detail) => {
    it(`displays the detail message for HTTP ${status}`, async () => {
      mockedApi(api).verifyOtp.mockRejectedValueOnce(apiError(status, detail));

      const { getNavigation } = mountScreen();
      fireEvent.changeText(getInput(), '000000');
      await act(async () => {
        fireEvent.press(screen.getByText('Verify & Continue'));
      });

      expect(await screen.findByText(detail)).toBeOnTheScreen();
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('OtpEntry');
      expect(await getStoredToken()).toBeNull();
    });
  });

  it('falls back to the Error.message text for non-Api errors (network failure)', async () => {
    mockedApi(api).verifyOtp.mockRejectedValueOnce(new Error('Network request failed'));

    mountScreen();
    fireEvent.changeText(getInput(), '111222');
    await act(async () => {
      fireEvent.press(screen.getByText('Verify & Continue'));
    });

    expect(await screen.findByText('Network request failed')).toBeOnTheScreen();
  });

  it('falls back to a generic message when a non-Error value is thrown', async () => {
    mockedApi(api).verifyOtp.mockRejectedValueOnce('boom');

    mountScreen();
    fireEvent.changeText(getInput(), '111222');
    await act(async () => {
      fireEvent.press(screen.getByText('Verify & Continue'));
    });

    expect(await screen.findByText('Failed to verify OTP.')).toBeOnTheScreen();
  });
});
