# Driver app testing

This document describes the test architecture, how to run the suites,
the mocking conventions, and where to add new tests.

## Layout

Two Jest projects coexist in `jest.config.js`:

| Project | Runner          | Files                                  | Scope                                                                |
| ------- | --------------- | -------------------------------------- | -------------------------------------------------------------------- |
| `unit`  | `ts-jest` (Node) | `src/__tests__/**/*.test.ts`           | Pure-TS unit tests for stores, config validation, JWT parsing, etc. |
| `rntl`  | `jest-expo` (jsdom) | `src/__tests__/rntl/**/*.rntl.test.tsx` | React Native Testing Library suites for screens and navigation.     |

Shared mocks for native modules (AsyncStorage, expo-secure-store) live
under `src/__tests__/mocks/` and are wired via `moduleNameMapper`.

The RNTL project also re-applies `react-native/jest/setup.js` and
`jest-expo/src/preset/setup.js` in `setupFiles` because Jest replaces
(not merges) array fields when a project overrides them.

## Running tests

```bash
cd driver-app
npm install            # first time
npm test               # both projects
npm run test:serial    # both projects serially (pilot/CI hang triage)
npm run test:open-handles # serial run with Jest open-handle diagnostics
npm run test:unit      # ts-jest only
npm run test:rntl      # rntl only
npm run test:coverage  # both projects + coverage report (enforces thresholds)
```

Coverage HTML lands in `driver-app/coverage/lcov-report/index.html`.

For pilot-readiness verification, run the serial suite and open-handle
check exactly as follows:

```bash
cd driver-app
npm test -- --runInBand
npm test -- --runInBand --detectOpenHandles
```

The `test:serial` and `test:open-handles` scripts are aliases for these
commands. The open-handle run is intentionally slower because Jest tracks
async resources; it should still finish with a normal pass/fail result and
without serious open-handle reports. Unit and screen tests must mock API
calls and native storage rather than depending on a live backend.

## Coverage thresholds

The repository-wide floor is set in `jest.config.js`:

```js
coverageThreshold: {
  global: { statements: 82, branches: 67, functions: 73, lines: 83 },
},
```

These are pinned a few points below the current numbers so routine
refactors don't flap CI. **Bump them up after any meaningful coverage
improvement** — they are intended to ratchet, not to absorb regressions.
A drop below these numbers fails `npm run test:coverage` and the
`driver-app` CI job in `.github/workflows/ci.yml`.

## Test utilities (`src/__tests__/rntl/test-utils/`)

| Helper                            | Purpose                                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `renderWithProviders`             | Wraps a tree in `PaperProvider` + `SafeAreaProvider` + `ProtocolFlowProvider`. Each layer is opt-out. |
| `renderScreen`                    | Mounts one screen inside a real `NavigationContainer` + native-stack with optional sibling stub routes. |
| `apiMock` / `mockedApi` / `apiError` | Typed helpers for the per-test `jest.mock('../../api')` pattern.                                       |
| `createProtocolFlowController` / `ProtocolFlowSpy` | Inspector for tests that need to read or seed live `ProtocolFlowContext` value (used by the integration suite). |

Always import from the barrel: `import { renderScreen, mockedApi } from '../test-utils';`.

## Mocking conventions

### Per-screen suites

Every per-screen RNTL suite mocks `useProtocolFlow` (and usually
`useProtocolRouteGuard`) at module level so the screen can be driven in
isolation without the real provider's effects re-firing across renders.
Pattern:

```ts
jest.mock('../../../navigation/ProtocolFlowContext', () => {
  const actual = jest.requireActual('../../../navigation/ProtocolFlowContext');
  return {
    ...actual,
    useProtocolFlow: () => ({ /* stable seed */ }),
  };
});
jest.mock('../../../navigation/useProtocolRouteGuard', () => ({
  useProtocolRouteGuard: jest.fn(),
}));
```

API calls are mocked per-test via `jest.mock('../../../api')` plus
`mockedApi(api).foo.mockResolvedValueOnce(...)`. Telemetry is mocked
to silence analytics network noise.

### Cross-screen integration suite

`navigation.transitions.rntl.test.tsx` deliberately does **not** mock
`useProtocolFlow` — it stands up the real `ProtocolFlowProvider` and
drives state via `ProtocolFlowController` so the route guard and the
state machine are exercised end-to-end.

**Caveat — `SafetyGate` cannot be mounted against the real provider.**
The screen's mount-time effect depends on `markSafetyGateViewed`, and
that callback's identity changes on every provider re-render, so the
effect re-fires after each `setState` and loops forever. The integration
suite therefore stops at `VehicleConfirm` and uses a stub for
`SafetyGate`. The SafetyGate transition itself is fully covered by its
own per-screen suite. Fixing the underlying hook (memoising the
callbacks with `useCallback` or exposing them via a stable ref) would
let us extend the integration chain further.

## Adding a new screen test

1. Drop the file under `src/__tests__/rntl/screens/` named
   `<Screen>.rntl.test.tsx`.
2. Mock the api module (`jest.mock('../../../api')`) and the
   protocol-flow hooks (see pattern above) at the top.
3. Import `renderScreen` from `../test-utils` and mount the screen
   with appropriate `siblings` for any routes it can navigate to.
4. Run `npm run test:rntl -- --testPathPattern <Screen>` while
   iterating.
5. Run `npm run test:coverage` before pushing — it enforces the
   thresholds locally and matches what CI runs.

## CI

The `driver-app` job in `.github/workflows/ci.yml` runs on every PR
against `main`:

1. `npm ci`
2. `npm run test:coverage` (both Jest projects + threshold enforcement)
3. Uploads `driver-app/coverage/` as a build artifact.

The job is included in the `required-checks` gate, so failures block
PR merges.

> **Known follow-up — `tsc --noEmit` is not yet wired into CI.** The
> driver app inherits a backlog of pre-existing TypeScript errors in
> the test suites (mostly around `RootStackParamList` parametric typing
> and the `renderScreen` `providerOptions.innerWrapper` type). Adding
> `tsc --noEmit` to this CI job would block all PRs until that backlog
> is cleared. Track the cleanup as a separate task; once the suites
> are clean, add a `typecheck` script to `package.json` and a `Type
> check (tsc)` step to the `driver-app` CI job.
