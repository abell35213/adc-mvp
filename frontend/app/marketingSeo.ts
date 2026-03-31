import type { Metadata } from "next";

const siteUrl = "https://www.adc-mvp.com";

export function buildPageMetadata(
  title: string,
  description: string,
  path: string,
): Metadata {
  const canonical = `${siteUrl}${path}`;
  return {
    title,
    description,
    alternates: {
      canonical,
    },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: "ADC",
      type: "website",
    },
  };
}
