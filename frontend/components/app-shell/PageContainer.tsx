import type { ReactNode } from "react";
import { cn } from "@/lib/design/utilities";
export function PageContainer({ children, wide=false }: { children: ReactNode; wide?: boolean }) { return <main id="main-content" tabIndex={-1} className={cn("w-full px-4 py-6 outline-none sm:px-6 lg:px-8", wide ? "max-w-none" : "mx-auto max-w-7xl")}>{children}</main>; }
