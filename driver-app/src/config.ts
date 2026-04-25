/**
 * Centralized runtime configuration for the driver app.
 *
 * The Expo build pipeline injects ``process.env.EXPO_PUBLIC_*`` variables at
 * bundle time. Wrap them here so callers don't have to re-implement the
 * trailing-slash trim or the localhost fallback in three different modules.
 */

const RAW_API_BASE_URL =
  // ``process.env`` is replaced by Metro/Expo at build time. Reading from a
  // typed indexer keeps TypeScript happy without us having to depend on
  // ``@types/node`` for a single env var.
  (process.env as Record<string, string | undefined>).EXPO_PUBLIC_API_BASE_URL ??
  'http://localhost:8000';

/**
 * Base URL of the ADC backend, with any trailing slash stripped so callers can
 * always concatenate ``${API_BASE_URL}/some/path`` without producing
 * double-slashes.
 */
export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/$/, '');
