export type TrackingPayload = {
  event: string;
  location: string;
  label: string;
};

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
  }
}

export function trackCtaClick(payload: TrackingPayload) {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new CustomEvent("adc:cta-click", { detail: payload }));

  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push({
      event: payload.event,
      cta_location: payload.location,
      cta_label: payload.label,
    });
  }
}
