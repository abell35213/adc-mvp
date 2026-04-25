/**
 * Setup file for the RNTL (React Native Testing Library) Jest project.
 *
 * Loaded *after* the test framework is installed (``setupFilesAfterEnv``),
 * so it can reference Jest globals like ``jest.mock`` and register matcher
 * extensions.
 *
 * Responsibilities:
 *   - Wire up React Native module mocks that are awkward to render in
 *     jsdom (Reanimated, gesture-handler).
 *   - Silence noisy console output that the underlying libraries emit
 *     during teardown but that does not represent a real test failure.
 *
 * NOTE: ``@testing-library/react-native`` v12.4+ ships built-in jest
 * matchers (``toBeOnTheScreen``, ``toHaveTextContent``, etc.) so the
 * legacy ``@testing-library/jest-native`` package is intentionally not
 * installed.
 */

// Reanimated ships an official Jest mock that replaces its native
// bindings with no-op JS implementations. Without it any screen that
// transitively imports reanimated (e.g. via ``react-native-paper``
// animations) will fail to load.
jest.mock('react-native-reanimated', () =>
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('react-native-reanimated/mock'),
);

// ``react-native-gesture-handler`` exports a JS-only jestSetup helper
// that registers stubs for native gesture handlers. Required by
// react-navigation's native-stack on first render.
// eslint-disable-next-line @typescript-eslint/no-require-imports
require('react-native-gesture-handler/jestSetup');

export {};
