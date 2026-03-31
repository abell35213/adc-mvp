"use client";

import Link from "next/link";
import { trackCtaClick } from "@/lib/tracking";

type TrackedCtaProps = {
  href: string;
  label: string;
  location: string;
  eventName?: string;
  className?: string;
};

export default function TrackedCta({
  href,
  label,
  location,
  eventName = "marketing_cta_click",
  className,
}: TrackedCtaProps) {
  return (
    <Link
      href={href}
      className={
        className ??
        "inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
      }
      data-track-event={eventName}
      data-track-location={location}
      data-track-label={label}
      onClick={() =>
        trackCtaClick({
          event: eventName,
          location,
          label,
        })
      }
    >
      {label}
    </Link>
  );
}
