import Image from "next/image";

export type AvatarChipSize = "sm" | "md" | "lg";

export interface AvatarChipProps {
  name: string;
  subtitle?: string;
  src?: string;
  size?: AvatarChipSize;
  className?: string;
}

const AVATAR_SIZE: Record<AvatarChipSize, string> = {
  sm: "h-7 w-7 text-[11px]",
  md: "h-9 w-9 text-xs",
  lg: "h-11 w-11 text-sm",
};

export default function AvatarChip({ name, subtitle, src, size = "md", className }: AvatarChipProps) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className={["inline-flex items-center gap-2 rounded-full border border-border-default bg-surface-muted px-2 py-1", className].filter(Boolean).join(" ")}>
      {src ? (
        <Image
          src={src}
          alt={name}
          width={44}
          height={44}
          className={["rounded-full object-cover", AVATAR_SIZE[size]].join(" ")}
        />
      ) : (
        <span className={["inline-flex items-center justify-center rounded-full bg-accent-soft font-semibold text-accent", AVATAR_SIZE[size]].join(" ")}>
          {initials}
        </span>
      )}
      <span className="leading-tight">
        <span className="block text-sm font-medium text-text-primary">{name}</span>
        {subtitle ? <span className="block text-xs text-text-secondary">{subtitle}</span> : null}
      </span>
    </div>
  );
}
