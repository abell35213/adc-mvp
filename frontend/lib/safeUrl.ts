/** Helpers for safely opening URLs returned by the backend.
 *
 * Export-download URLs are presigned URLs to S3/CloudFront and are returned by
 * the API. Without validation a malicious or compromised export-link payload
 * could trigger an open-redirect to an attacker-controlled site (e.g. a
 * phishing page styled to look like the app). We therefore allow only:
 *
 *   1. Same-origin URLs (the user is already on the app).
 *   2. URLs whose host matches an allow-list configured at build time via
 *      ``NEXT_PUBLIC_EXPORT_DOWNLOAD_HOSTS`` (comma-separated hostnames or
 *      hostname suffixes prefixed with ``.``, e.g. ``s3.amazonaws.com,.cloudfront.net``).
 *
 * Anything else is rejected and the caller is expected to surface an error.
 */

function parseAllowedHosts(): string[] {
  // The env var is read at build time by Next.js for browser bundles.
  const raw = process.env.NEXT_PUBLIC_EXPORT_DOWNLOAD_HOSTS ?? "";
  return raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s.length > 0);
}

/** Returns true if *url* is safe to open in a new tab. */
export function isAllowedDownloadUrl(url: string): boolean {
  if (!url || typeof url !== "string") return false;

  let parsed: URL;
  try {
    // ``URL`` requires a base for relative inputs — but presigned download URLs
    // should always be absolute. If the caller passed a relative path we treat
    // it as same-origin via the current ``window.location``.
    parsed = new URL(url, typeof window !== "undefined" ? window.location.href : undefined);
  } catch {
    return false;
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return false;
  }

  // Same-origin is always allowed.
  if (typeof window !== "undefined" && parsed.origin === window.location.origin) {
    return true;
  }

  const host = parsed.hostname.toLowerCase();
  for (const entry of parseAllowedHosts()) {
    if (entry.startsWith(".")) {
      // ``.example.com`` matches any sub-domain of example.com (and example.com itself).
      if (host === entry.slice(1) || host.endsWith(entry)) return true;
    } else if (host === entry) {
      return true;
    }
  }
  return false;
}

/** Open *url* in a new tab if it passes the allow-list, otherwise return false. */
export function safeOpenDownloadUrl(url: string): boolean {
  if (!isAllowedDownloadUrl(url)) return false;
  // ``noopener,noreferrer`` prevents the opened page from accessing
  // ``window.opener`` (reverse-tabnabbing protection).
  window.open(url, "_blank", "noopener,noreferrer");
  return true;
}
