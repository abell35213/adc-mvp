/**
 * Helpers for the per-test API mock pattern (option **(a)** from the
 * planning doc): each test file declares
 *
 *   jest.mock('../../api');
 *
 * at the top level, then uses {@link mockedApi} to obtain a fully typed
 * `jest.Mocked<typeof api>` view, and {@link apiError} to construct the
 * `ApiRequestError` instances that the production code throws.
 *
 * These helpers do NOT call `jest.mock` themselves — that has to live at
 * the top of the test file so Jest can hoist it before module evaluation.
 *
 * `ApiRequestError` is loaded via `jest.requireActual` so that test files
 * which auto-mock the api module still see the real error class — the
 * class-with-state semantics matter for `instanceof` checks and for
 * surfacing the `status` / `message` fields the screens read.
 */

import type * as ApiModule from '../../../api';

const actualApi = jest.requireActual<typeof ApiModule>('../../../api');

/** Re-export of the real `ApiRequestError` class for `instanceof` checks. */
export const ApiRequestError = actualApi.ApiRequestError;

/**
 * Build an {@link ApiRequestError} matching the shape the real `request`
 * helper produces on non-2xx responses.
 *
 * @param status  HTTP status code (e.g. 401, 404, 422, 500).
 * @param detail  Optional `detail` body field; falls back to a generic
 *                "Request failed" message when omitted.
 */
export function apiError(
  status: number,
  detail?: string,
): InstanceType<typeof ApiRequestError> {
  return new ApiRequestError(detail ?? 'Request failed', status);
}

/**
 * Return the `jest.Mocked<typeof api>` view of the api module.
 *
 * MUST be called from a test file that declared
 * ``jest.mock('../../api')`` at the top level — otherwise the import
 * resolves to the real module and `jest.mocked` will not auto-mock its
 * functions.
 *
 * Example:
 *
 *   jest.mock('../../api');
 *   import * as api from '../../api';
 *   import { mockedApi, apiError } from './test-utils';
 *
 *   beforeEach(() => {
 *     mockedApi(api).requestOtp.mockResolvedValue(undefined as never);
 *   });
 *
 *   it('surfaces the OTP failure', async () => {
 *     mockedApi(api).requestOtp.mockRejectedValueOnce(apiError(429, 'slow'));
 *     // …
 *   });
 */
export function mockedApi(
  apiModule: typeof ApiModule,
): jest.Mocked<typeof ApiModule> {
  return jest.mocked(apiModule);
}

/**
 * Resets all jest.fn() implementations on the api module back to bare
 * `jest.fn()` returning `undefined`. Useful inside `beforeEach` blocks.
 *
 * Most tests can rely on the global `clearMocks: true` Jest option
 * (see `jest.config.js`), but this is provided for suites that want to
 * be explicit.
 */
export function resetApiMocks(apiModule: typeof ApiModule): void {
  const mocked = jest.mocked(apiModule);
  for (const key of Object.keys(mocked) as Array<keyof typeof mocked>) {
    const value = mocked[key];
    if (typeof value === 'function' && 'mockReset' in value) {
      (value as jest.Mock).mockReset();
    }
  }
}
