import Image from "next/image";

type LogoVariant = "full" | "mark";

interface LogoProps {
  variant?: LogoVariant;
  /** Rendered height in pixels. Width is derived from the source aspect ratio. */
  height?: number;
  className?: string;
  /** When true, the logo is decorative and gets an empty alt. */
  decorative?: boolean;
  priority?: boolean;
}

const SOURCES: Record<LogoVariant, { src: string; aspect: number }> = {
  // 480x520 viewBox
  full: { src: "/brand/adc-logo.svg", aspect: 480 / 520 },
  // 360x360 viewBox
  mark: { src: "/brand/adc-mark.svg", aspect: 1 },
};

export function Logo({
  variant = "full",
  height = 40,
  className,
  decorative = false,
  priority = false,
}: LogoProps) {
  const { src, aspect } = SOURCES[variant];
  const width = Math.round(height * aspect);
  return (
    <Image
      src={src}
      alt={decorative ? "" : "ADC – Accident Defense Center"}
      width={width}
      height={height}
      priority={priority}
      className={className}
    />
  );
}
