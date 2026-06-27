/**
 * `renderScreen` — mount a single screen component inside a real
 * `NavigationContainer` + native-stack so that ``useNavigation``,
 * ``useRoute``, navigation lifecycle events, and route-param typing all
 * behave exactly as they would at runtime.
 *
 * Usage:
 *
 *   const { screen, getNavigation } = renderScreen({
 *     name: 'OtpEntry',
 *     component: OtpEntryScreen,
 *     params: { phoneE164: '+15551234567' },
 *     siblings: [{ name: 'DriverHome', component: DriverHomeScreen }],
 *   });
 *
 *   // …interact…
 *   expect(getNavigation()?.getCurrentRoute()?.name).toBe('DriverHome');
 *
 * Sibling routes are stub `<View testID="route-stub-{name}" />` screens by
 * default; pass real components to test cross-screen flow.
 */

import { ReactElement, ComponentType, useEffect } from 'react';
import { View } from 'react-native';
import { NavigationContainer, NavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { RootStackParamList } from '../../../navigation/types';
import {
  renderWithProviders,
  RenderWithProvidersOptions,
} from './renderWithProviders';

type AnyScreenName = keyof RootStackParamList;

export type SiblingRoute = {
  name: AnyScreenName;
  component?: ComponentType<any>;
};

export type RenderScreenOptions<RouteName extends AnyScreenName> = {
  /** The screen route name being mounted. */
  name: RouteName;
  /** The screen component implementation. */
  component: ComponentType<any>;
  /**
   * Initial params for the mounted route. Required-shape per
   * `RootStackParamList[RouteName]`.
   */
  params?: RootStackParamList[RouteName];
  /**
   * Other route names that the screen under test may navigate to. They are
   * registered in the stack with simple stub components unless an explicit
   * component is supplied. Stubs render
   * ``<View testID="route-stub-{name}" />`` so a test can assert on them
   * without importing real screens.
   */
  siblings?: SiblingRoute[];
  /**
   * Optional spy invoked on every navigation state change. Lets tests
   * observe the live navigation state (current route, history) without
   * reaching for the ref.
   */
  onStateChange?: NonNullable<
    React.ComponentProps<typeof NavigationContainer>['onStateChange']
  >;
  /** Provider toggles, forwarded to {@link renderWithProviders}. */
  providerOptions?: RenderWithProvidersOptions;
};

export type RenderScreenResult = {
  screen: ReturnType<typeof renderWithProviders>;
  /**
   * Returns the current navigation container ref. ``null`` until the
   * container has mounted; tests should call after the first paint.
   */
  getNavigation: () => NavigationContainerRef<RootStackParamList> | null;
};

const RouteStub = ({ name }: { name: AnyScreenName }) => (
  <View testID={`route-stub-${name}`} />
);

export function renderScreen<RouteName extends AnyScreenName>(
  options: RenderScreenOptions<RouteName>,
): RenderScreenResult {
  const { name, component, params, siblings = [], providerOptions, onStateChange } =
    options;
  const Stack = createNativeStackNavigator<RootStackParamList>();
  let navRef: NavigationContainerRef<RootStackParamList> | null = null;

  const NavRefBridge = ({ navigation }: { navigation: NavigationContainerRef<RootStackParamList> }) => {
    useEffect(() => {
      navRef = navigation;
      return () => {
        navRef = null;
      };
    }, [navigation]);
    return null;
  };

  const tree: ReactElement = (
    <NavigationContainer
      ref={(ref) => {
        navRef = ref as NavigationContainerRef<RootStackParamList> | null;
      }}
      onStateChange={onStateChange}
    >
      <Stack.Navigator initialRouteName={name as AnyScreenName}>
        <Stack.Screen
          name={name as AnyScreenName}
          component={component as ComponentType<object>}
          initialParams={params as object | undefined}
        />
        {siblings.map((sibling) => (
          <Stack.Screen
            key={sibling.name}
            name={sibling.name}
            component={
              (sibling.component ?? (() => <RouteStub name={sibling.name} />)) as ComponentType<object>
            }
          />
        ))}
      </Stack.Navigator>
    </NavigationContainer>
  );

  // Touch the bridge symbol so unused-import linters stay quiet without
  // actually rendering it (it is reserved for future expansion if we need
  // to expose more nav internals to tests).
  void NavRefBridge;

  const screen = renderWithProviders(tree, providerOptions);

  return {
    screen,
    getNavigation: () => navRef,
  };
}
