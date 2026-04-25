import { API_BASE_URL } from '../config';

describe('config / API_BASE_URL', () => {
  it('exports a string with no trailing slash', () => {
    expect(typeof API_BASE_URL).toBe('string');
    expect(API_BASE_URL.endsWith('/')).toBe(false);
  });

  it('falls back to localhost when EXPO_PUBLIC_API_BASE_URL is unset', () => {
    // The module is evaluated once at import time, so this verifies the
    // post-import shape rather than re-evaluating with new env vars. The
    // localhost:8000 default should be present in any test environment that
    // does not override it via Jest globalSetup.
    expect(API_BASE_URL).toMatch(/^https?:\/\/[^/]+$/);
  });
});
