/**
 * Smoke tests for the shared RNTL test utilities.
 *
 * Each test exercises one utility in isolation so a regression points
 * directly at the helper, not at a downstream screen suite.
 */

import { act, fireEvent, screen } from '@testing-library/react-native';
import { Button, Text } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';

// Per-test API mock — the canonical "option (a)" pattern.
jest.mock('../../api');
import * as api from '../../api';

import { useProtocolFlow } from '../../navigation/ProtocolFlowContext';
import {
  ApiRequestError,
  ProtocolFlowSpy,
  apiError,
  createProtocolFlowController,
  mockedApi,
  renderScreen,
  renderWithProviders,
  resetApiMocks,
} from './test-utils';

describe('renderWithProviders', () => {
  it('mounts a child component with the default provider stack', () => {
    renderWithProviders(<Text testID="child">hi</Text>);
    expect(screen.getByTestId('child')).toBeOnTheScreen();
  });

  it('omits ProtocolFlowProvider when withProtocolFlow=false', () => {
    // useProtocolFlow throws when its provider is missing — verify that
    // the toggle actually removes the provider by mounting a child that
    // consumes the hook.
    const Consumer = () => {
      useProtocolFlow();
      return null;
    };

    expect(() =>
      renderWithProviders(<Consumer />, { withProtocolFlow: false }),
    ).toThrow(/useProtocolFlow must be used within ProtocolFlowProvider/);
  });

  it('matches a stable snapshot for a trivial tree', () => {
    const { toJSON } = renderWithProviders(<Text testID="snap">snap</Text>);
    expect(toJSON()).toMatchSnapshot();
  });
});

describe('renderScreen', () => {
  const Greeting = () => <Text testID="greeting">on the screen</Text>;

  it('mounts a screen inside a real navigator', () => {
    const { getNavigation } = renderScreen({
      name: 'PhoneEntry',
      component: Greeting,
    });

    expect(screen.getByTestId('greeting')).toBeOnTheScreen();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('PhoneEntry');
  });

  it('navigates to a sibling stub route', () => {
    const Jumper = () => {
      const navigation = useNavigation<{ navigate: (name: string) => void }>();
      return (
        <Button
          testID="jump"
          title="jump"
          onPress={() => navigation.navigate('DriverHome')}
        />
      );
    };

    const { getNavigation } = renderScreen({
      name: 'PhoneEntry',
      component: Jumper,
      siblings: [{ name: 'DriverHome' }],
    });

    act(() => {
      fireEvent.press(screen.getByTestId('jump'));
    });

    expect(screen.getByTestId('route-stub-DriverHome')).toBeOnTheScreen();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
  });

  it('forwards initial route params via useRoute()', () => {
    const ParamReader = () => {
      const route = useRoute();
      const params = route.params as { phoneE164?: string } | undefined;
      return <Text testID="phone">{params?.phoneE164 ?? 'none'}</Text>;
    };

    renderScreen({
      name: 'OtpEntry',
      component: ParamReader,
      params: { phoneE164: '+15551234567' },
    });

    expect(screen.getByTestId('phone')).toHaveTextContent('+15551234567');
  });
});

describe('apiMock helpers', () => {
  beforeEach(() => {
    resetApiMocks(api);
  });

  it('apiError produces an ApiRequestError with the provided status + detail', () => {
    const err = apiError(404, 'not found');
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.status).toBe(404);
    expect(err.message).toBe('not found');
  });

  it('apiError defaults the detail message when omitted', () => {
    const err = apiError(500);
    expect(err.message).toBe('Request failed');
  });

  it('mockedApi exposes typed jest.fn() implementations for every export', async () => {
    const mocked = mockedApi(api);
    mocked.requestOtp.mockResolvedValueOnce(undefined as never);

    await api.requestOtp('+15550001111');

    expect(mocked.requestOtp).toHaveBeenCalledWith('+15550001111');
  });

  it('mockedApi can simulate a rejected request via apiError', async () => {
    mockedApi(api).verifyOtp.mockRejectedValueOnce(apiError(401, 'bad code'));
    await expect(api.verifyOtp('+15550001111', '000000')).rejects.toMatchObject({
      status: 401,
      message: 'bad code',
    });
  });
});

describe('protocolFlowController', () => {
  it('captures the live ProtocolFlowContext value and supports mutation', () => {
    const controller = createProtocolFlowController();

    renderWithProviders(<ProtocolFlowSpy controller={controller} />);

    expect(controller.current).not.toBeNull();
    expect(controller.current?.protocolContext.vehicleResolved).toBe(false);

    act(() => {
      controller.current?.resolveVehicle({
        vehicleId: 'veh-123',
        method: 'qr',
        qrToken: 'tok',
      });
    });

    expect(controller.current?.protocolContext.vehicleResolved).toBe(true);
    expect(controller.current?.protocolContext.vehicleId).toBe('veh-123');
  });
});
