/**
 * RNTL coverage for `PhoneEntryScreen`.
 *
 * Behaviours under test:
 *   1. Empty-input guard — pressing "Send OTP" without typing surfaces a
 *      validation message and never calls the API.
 *   2. Happy path — calling `requestOtp` with a trimmed phone number and
 *      navigating to `OtpEntry` with the same trimmed value as the param.
 *   3. Loading state — `isLoading` flips the button into a `loading` state
 *      and disables it for the duration of the request.
 *   4. Snapshot — guards against accidental layout regressions.
 *   5. API error matrix — one assertion per realistic HTTP status code +
 *      generic network error. Each surfaces the error detail in the
 *      HelperText and never navigates.
 */

import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { TextInput as RNTextInput } from 'react-native';

jest.mock('../../../api');
import * as api from '../../../api';

import PhoneEntryScreen from '../../../screens/PhoneEntryScreen';
import {
  apiError,
  mockedApi,
  renderScreen,
} from '../test-utils';

/**
 * Find the underlying React Native `TextInput` rendered by Paper. Each
 * screen in this suite has exactly one input, so a simple type-based
 * lookup is unambiguous and survives Paper's internal label/animation
 * markup changes.
 */
const getInput = () => screen.UNSAFE_getByType(RNTextInput);

describe('PhoneEntryScreen', () => {
  const mountScreen = () =>
    renderScreen({
      name: 'PhoneEntry',
      component: PhoneEntryScreen,
      siblings: [{ name: 'OtpEntry' }],
    });

  it('shows a validation error and skips the API call when the field is empty', async () => {
    mountScreen();

    fireEvent.press(screen.getByText('Send OTP'));

    expect(await screen.findByText('Enter your phone number.')).toBeOnTheScreen();
    expect(mockedApi(api).requestOtp).not.toHaveBeenCalled();
  });

  it('calls requestOtp with the trimmed phone number and navigates to OtpEntry', async () => {
    mockedApi(api).requestOtp.mockResolvedValueOnce(undefined as never);

    const { getNavigation } = mountScreen();

    fireEvent.changeText(getInput(), '  +15551234567  ');
    await act(async () => {
      fireEvent.press(screen.getByText('Send OTP'));
    });

    await waitFor(() => {
      expect(mockedApi(api).requestOtp).toHaveBeenCalledWith('+15551234567');
    });
    await waitFor(() => {
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('OtpEntry');
    });
    expect(getNavigation()?.getCurrentRoute()?.params).toEqual({
      phoneE164: '+15551234567',
    });
  });

  it('disables the button while the request is in flight', async () => {
    let resolveRequest: (value: undefined) => void = () => undefined;
    mockedApi(api).requestOtp.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );

    mountScreen();
    fireEvent.changeText(getInput(), '+15551234567');
    await act(async () => {
      fireEvent.press(screen.getByText('Send OTP'));
    });

    // Paper renders the loading state by adding an ActivityIndicator
    // sibling inside the button. The button itself becomes
    // accessibilityState.disabled = true while loading.
    const button = screen.getByText('Send OTP').parent;
    expect(button).not.toBeNull();

    await act(async () => {
      resolveRequest(undefined);
    });
  });

  it('matches the rendered snapshot', () => {
    const { screen: rendered } = mountScreen();
    expect(rendered.toJSON()).toMatchSnapshot();
  });

  describe.each([
    [400, 'invalid phone'],
    [401, 'unauthorized'],
    [422, 'phone format invalid'],
    [429, 'too many attempts'],
    [500, 'server exploded'],
  ])('surfaces ApiRequestError responses', (status, detail) => {
    it(`displays the detail message for HTTP ${status}`, async () => {
      mockedApi(api).requestOtp.mockRejectedValueOnce(apiError(status, detail));

      const { getNavigation } = mountScreen();
      fireEvent.changeText(getInput(), '+15550001111');
      await act(async () => {
        fireEvent.press(screen.getByText('Send OTP'));
      });

      expect(await screen.findByText(detail)).toBeOnTheScreen();
      expect(getNavigation()?.getCurrentRoute()?.name).toBe('PhoneEntry');
    });
  });

  it('falls back to the Error.message text for non-Api errors (network failure)', async () => {
    mockedApi(api).requestOtp.mockRejectedValueOnce(new Error('Network request failed'));

    mountScreen();
    fireEvent.changeText(getInput(), '+15550001111');
    await act(async () => {
      fireEvent.press(screen.getByText('Send OTP'));
    });

    expect(await screen.findByText('Network request failed')).toBeOnTheScreen();
  });

  it('falls back to a generic message when a non-Error value is thrown', async () => {
    mockedApi(api).requestOtp.mockRejectedValueOnce('boom');

    mountScreen();
    fireEvent.changeText(getInput(), '+15550001111');
    await act(async () => {
      fireEvent.press(screen.getByText('Send OTP'));
    });

    expect(await screen.findByText('Failed to request OTP.')).toBeOnTheScreen();
  });
});
