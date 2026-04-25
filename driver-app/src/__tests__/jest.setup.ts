/**
 * Global Jest setup for the driver-app suite.
 *
 * React Native code-paths read ``__DEV__`` to gate dev-only logging.
 * Define it here so the source modules don't need to guard against the
 * symbol being missing under Node.
 */
// @ts-expect-error - __DEV__ is a React Native runtime global, not in @types/node.
globalThis.__DEV__ = false;

export {};
