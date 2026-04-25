/**
 * Minimal Jest setup for the driver app.
 *
 * Goals:
 *   - Run pure TypeScript unit tests (config validation, JSON shape guards,
 *     JWT expiry parsing, store-hydration logic) without spinning up the full
 *     React Native runtime.
 *   - Mock the native modules that the code under test imports
 *     (``@react-native-async-storage/async-storage`` and ``expo-secure-store``)
 *     so we never load a binary that won't run under Node.
 *
 * Out of scope (deferred): full ``jest-expo`` preset + React Native Testing
 * Library for screen-level tests. Once that's wired up, this config can be
 * extended (or per-suite project configs can be added) without rewriting it.
 */

/** @type {import('jest').Config} */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/__tests__/**/*.test.ts', '**/__tests__/**/*.test.tsx'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  moduleNameMapper: {
    // Native modules — replaced with lightweight in-memory mocks living next
    // to the tests so suites stay deterministic.
    '^@react-native-async-storage/async-storage$':
      '<rootDir>/src/__tests__/mocks/asyncStorage.ts',
    '^expo-secure-store$': '<rootDir>/src/__tests__/mocks/secureStore.ts',
  },
  setupFiles: ['<rootDir>/src/__tests__/jest.setup.ts'],
  // Keep test runs fast — these are unit tests, not integration.
  testTimeout: 5000,
  clearMocks: true,
};
