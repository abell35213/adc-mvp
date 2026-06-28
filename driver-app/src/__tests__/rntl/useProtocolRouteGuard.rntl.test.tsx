/**
 * RNTL coverage for `useProtocolRouteGuard`.
 *
 * The guard runs inside `useFocusEffect`. When the focused route is
 * not yet accessible (its prerequisites in `PROTOCOL_ROUTE_ORDER` are
 * not all in `completedRoutes`), it `replace`s navigation to the
 * first incomplete route — unless the first incomplete route is the
 * current route, in which case it does nothing (avoiding an infinite
 * replace loop).
 *
 * Behaviours under test:
 *   1. With all prerequisites complete, the guard does NOT replace.
 *   2. With a missing prerequisite, the guard `replace`s to the
 *      first incomplete route.
 *   3. The guard never replaces a screen with itself even when the
 *      screen is the first incomplete route (e.g. mounting
 *      `IncidentConfirm` with empty `completedRoutes`).
 *   4. When the focused route is mid-flow (e.g. `MediaCapture`) but
 *      an earlier route (e.g. `SceneFacts`) is missing, it replaces
 *      to that earlier route.
 *
 * The test rigs use `renderScreen` to mount a tiny probe component
 * that simply invokes the guard — keeping the harness free of any
 * specific screen's effects.
 */

import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { View } from 'react-native';

import { ProtocolRouteName } from '../../navigation/protocolFlow';
import { useProtocolRouteGuard } from '../../navigation/useProtocolRouteGuard';
import { RootStackParamList } from '../../navigation/types';
import { renderScreen } from './test-utils';

let mockCompletedRoutes = new Set<ProtocolRouteName>();

jest.mock('../../navigation/ProtocolFlowContext', () => {
  const actual = jest.requireActual('../../navigation/ProtocolFlowContext');
  return {
    ...actual,
    useProtocolFlow: () => ({
      completedRoutes: mockCompletedRoutes,
    }),
  };
});

const setCompletedRoutes = (routes: ProtocolRouteName[]) => {
  mockCompletedRoutes = new Set(routes);
};

const ALL_BEFORE_MEDIA: ProtocolRouteName[] = [
  'IncidentConfirm',
  'VehicleConfirm',
  'SafetyGate',
  'IncidentStartLoading',
  'InstructionStep',
  'SceneFacts',
  'ThirdPartyInfo',
];

/**
 * Probe component: invokes the guard and exposes the live
 * `replace` calls via the captured `replaceSpy`.
 */
function makeProbe(routeName: ProtocolRouteName, replaceSpy: jest.Mock) {
  return function GuardProbe() {
    const navigation =
      useNavigation<NativeStackNavigationProp<RootStackParamList>>();
    const wrappedNav = {
      replace: (target: ProtocolRouteName) => {
        replaceSpy(target);
        // Forward to the real navigator so `getCurrentRoute()` reflects
        // the effect — gives us a second axis of verification.
        (navigation.replace as (screen: ProtocolRouteName) => void)(target);
      },
    };
    useProtocolRouteGuard(routeName, wrappedNav);
    return <View testID={`probe-${routeName}`} />;
  };
}

describe('useProtocolRouteGuard', () => {
  beforeEach(() => {
    setCompletedRoutes([]);
  });

  it('does NOT replace when all prerequisites for the focused route are complete', async () => {
    setCompletedRoutes(ALL_BEFORE_MEDIA);
    const replaceSpy = jest.fn();

    const { getNavigation } = renderScreen({
      name: 'MediaCapture',
      component: makeProbe('MediaCapture', replaceSpy),
      siblings: [
        { name: 'IncidentConfirm' },
        { name: 'SceneFacts' },
      ],
    });

    expect(replaceSpy).not.toHaveBeenCalled();
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('MediaCapture');
  });

  it('replaces to the first incomplete route when a prerequisite is missing', async () => {
    // Mid-flow route mounted with the SceneFacts prerequisite missing.
    setCompletedRoutes([
      'IncidentConfirm',
      'VehicleConfirm',
      'SafetyGate',
      'IncidentStartLoading',
      'InstructionStep',
    ]);
    const replaceSpy = jest.fn();

    const { getNavigation } = renderScreen({
      name: 'MediaCapture',
      component: makeProbe('MediaCapture', replaceSpy),
      siblings: [
        { name: 'SceneFacts' },
        { name: 'IncidentConfirm' },
      ],
    });

    expect(replaceSpy).toHaveBeenCalledWith('SceneFacts');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('SceneFacts');
  });

  it('never replaces a route with itself when the focused route IS the first incomplete one', async () => {
    // Empty `completedRoutes` → first incomplete is `IncidentConfirm`,
    // which is also the focused route. Replacing would recurse.
    setCompletedRoutes([]);
    const replaceSpy = jest.fn();

    renderScreen({
      name: 'IncidentConfirm',
      component: makeProbe('IncidentConfirm', replaceSpy),
    });

    expect(replaceSpy).not.toHaveBeenCalled();
  });

  it('redirects deep mid-flow routes back to the first incomplete prerequisite', async () => {
    // Nothing completed → mounting `Narrative` should kick the user
    // back to the start of the flow.
    setCompletedRoutes([]);
    const replaceSpy = jest.fn();

    const { getNavigation } = renderScreen({
      name: 'Narrative',
      component: makeProbe('Narrative', replaceSpy),
      siblings: [{ name: 'IncidentConfirm' }],
    });

    expect(replaceSpy).toHaveBeenCalledWith('IncidentConfirm');
    expect(getNavigation()?.getCurrentRoute()?.name).toBe('IncidentConfirm');
  });
});
