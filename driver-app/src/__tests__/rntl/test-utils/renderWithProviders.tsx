/**
 * `renderWithProviders` — RNTL render helper that wraps a UI tree in the
 * providers every driver-app screen depends on.
 *
 * By default we install:
 *   - `PaperProvider`           (react-native-paper theming, portal host)
 *   - `SafeAreaProvider`        (react-native-safe-area-context insets)
 *   - `ProtocolFlowProvider`    (the app-wide protocol state machine)
 *
 * Any of those layers can be opted out of via the options bag — useful when
 * a test wants to assert on a specific provider being absent (e.g. verifying
 * that `useProtocolFlow()` throws when its provider is missing).
 *
 * For tests that need real navigation, use the higher-level `renderScreen`
 * helper instead — it builds on top of this one.
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions, RenderResult } from '@testing-library/react-native';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ProtocolFlowProvider } from '../../../navigation/ProtocolFlowContext';

export type RenderWithProvidersOptions = Omit<RenderOptions, 'wrapper'> & {
  /** Wrap in {@link PaperProvider}. Default `true`. */
  withPaper?: boolean;
  /** Wrap in {@link SafeAreaProvider}. Default `true`. */
  withSafeArea?: boolean;
  /** Wrap in {@link ProtocolFlowProvider}. Default `true`. */
  withProtocolFlow?: boolean;
  /**
   * Optional additional wrapper inserted *inside* the standard providers
   * (closest to the rendered UI). Handy for things like a custom theme or
   * a test-specific context provider.
   */
  innerWrapper?: (children: ReactNode) => ReactElement;
};

const DEFAULT_OPTIONS: Required<
  Pick<
    RenderWithProvidersOptions,
    'withPaper' | 'withSafeArea' | 'withProtocolFlow'
  >
> = {
  withPaper: true,
  withSafeArea: true,
  withProtocolFlow: true,
};

const buildWrapper = (options: RenderWithProvidersOptions) => {
  const flags = { ...DEFAULT_OPTIONS, ...options };
  return function Wrapper({ children }: { children: ReactNode }) {
    let node: ReactNode = options.innerWrapper
      ? options.innerWrapper(children)
      : children;
    if (flags.withProtocolFlow) {
      node = <ProtocolFlowProvider>{node}</ProtocolFlowProvider>;
    }
    if (flags.withSafeArea) {
      node = <SafeAreaProvider>{node}</SafeAreaProvider>;
    }
    if (flags.withPaper) {
      node = <PaperProvider>{node}</PaperProvider>;
    }
    return <>{node}</>;
  };
};

export function renderWithProviders(
  ui: ReactElement,
  options: RenderWithProvidersOptions = {},
): RenderResult {
  return render(ui, { ...options, wrapper: buildWrapper(options) });
}
