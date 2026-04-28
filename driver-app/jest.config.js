/**
 * Jest setup for the driver app — multi-project configuration.
 *
 * Two test projects coexist:
 *
 *   1. **unit** (ts-jest / Node): pure TypeScript unit tests for stores,
 *      config validation, JWT parsing, etc. Fast and deterministic; never
 *      loads the React Native runtime.
 *
 *   2. **rntl** (jest-expo / jsdom): React Native Testing Library suites
 *      for screen-level coverage (auth flow, navigation transitions, API
 *      error paths). Files match ``*.rntl.test.tsx``.
 *
 * Run ``npm test`` to execute both projects, or
 * ``npm test -- --selectProjects unit`` / ``--selectProjects rntl`` to
 * scope a run to one suite.
 */

const sharedModuleNameMapper = {
  // Native modules — replaced with lightweight in-memory mocks living next
  // to the tests so suites stay deterministic across both projects.
  '^@react-native-async-storage/async-storage$':
    '<rootDir>/src/__tests__/mocks/asyncStorage.ts',
  '^expo-secure-store$': '<rootDir>/src/__tests__/mocks/secureStore.ts',
  // `@expo/vector-icons/MaterialCommunityIcons` transitively pulls in
  // `expo-font`/`expo-asset`/`expo-modules-core`, which don't resolve under
  // the `jest-expo` jsdom environment. Stub it with a Text-only renderer so
  // Paper components can inject icons during tests without warnings.
  '^@expo/vector-icons/MaterialCommunityIcons$':
    '<rootDir>/src/__tests__/mocks/materialCommunityIcons.tsx',
};

/** @type {import('jest').Config} */
module.exports = {
  // Top-level coverage knobs apply to every project. Per-project
  // ``collectCoverageFrom`` overrides scope which sources each runner
  // instruments, then Jest merges the maps in the final report.
  coverageReporters: ['text-summary', 'lcov', 'html'],
  // Repository-wide coverage floor. Values are pinned a few points
  // below the current numbers so routine refactors don't flap CI, but
  // large regressions (a deleted suite, a missed code path) will fail
  // the ``test:coverage`` script and the matching CI job. Bump these
  // up after meaningful coverage improvements.
  coverageThreshold: {
    global: {
      statements: 82,
      branches: 67,
      functions: 73,
      lines: 83,
    },
  },
  projects: [
    {
      displayName: 'unit',
      preset: 'ts-jest',
      testEnvironment: 'node',
      roots: ['<rootDir>/src'],
      // Existing pure-TS unit tests live directly under ``src/__tests__`` and
      // use ``*.test.ts``. Keep RNTL suites out of this project.
      testMatch: ['**/__tests__/**/*.test.ts'],
      testPathIgnorePatterns: ['/node_modules/', '<rootDir>/src/__tests__/rntl/'],
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
      moduleNameMapper: sharedModuleNameMapper,
      setupFiles: ['<rootDir>/src/__tests__/jest.setup.ts'],
      clearMocks: true,
      // The ts-jest project doesn't run a JSX-aware babel pass, so it can
      // only instrument plain ``.ts`` modules. ``.tsx`` (screens, context)
      // are covered by the rntl project below.
      collectCoverageFrom: [
        'src/**/*.ts',
        '!src/**/*.d.ts',
        '!src/**/*.tsx',
        '!src/__tests__/**',
        '!src/types/**',
      ],
    },
    {
      displayName: 'rntl',
      preset: 'jest-expo',
      // Don't restrict ``roots`` — jest-expo / Expo internals require the
      // default ``<rootDir>`` so their own sibling modules resolve. We
      // narrow the test surface via ``testMatch`` instead.
      testMatch: ['<rootDir>/src/__tests__/rntl/**/*.rntl.test.tsx'],
      moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
      moduleNameMapper: sharedModuleNameMapper,
      // jest-expo's preset registers ``react-native/jest/setup.js`` and
      // ``jest-expo/src/preset/setup.js`` in ``setupFiles``; Jest replaces
      // (not merges) array fields when a project overrides them, so we
      // re-list them here before adding our own jest.setup.ts.
      setupFiles: [
        require.resolve('react-native/jest/setup.js'),
        require.resolve('jest-expo/src/preset/setup.js'),
        '<rootDir>/src/__tests__/jest.setup.ts',
      ],
      setupFilesAfterEnv: ['<rootDir>/src/__tests__/rntl/setup.ts'],
      clearMocks: true,
      collectCoverageFrom: [
        'src/**/*.{ts,tsx}',
        '!src/**/*.d.ts',
        '!src/__tests__/**',
        '!src/types/**',
      ],
    },
  ],
};
