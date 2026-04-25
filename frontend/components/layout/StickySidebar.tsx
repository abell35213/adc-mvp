import type { ReactNode } from "react";

export interface StickySidebarProps {
  children: ReactNode;
  topOffsetClassName?: string;
  className?: string;
}

export default function StickySidebar({
  children,
  topOffsetClassName = "top-20",
  className,
}: StickySidebarProps) {
  return <aside className={["sticky space-y-3", topOffsetClassName, className].filter(Boolean).join(" ")}>{children}</aside>;
}
