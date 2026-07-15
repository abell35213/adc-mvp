import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/design/utilities";
import { disabled, focusRing, transition } from "@/lib/design/variants";

type Variant = "primary" | "secondary" | "quiet" | "destructive";
type Size = "sm" | "md" | "lg";
const variants: Record<Variant,string>={primary:"border-transparent bg-action-primary text-text-inverse hover:bg-action-primary-hover active:bg-action-primary-active",secondary:"border-border-default bg-action-secondary text-text-primary hover:bg-surface-subtle",quiet:"border-transparent bg-transparent text-text-secondary hover:bg-action-quiet hover:text-text-primary",destructive:"border-transparent bg-action-destructive text-text-inverse hover:bg-status-critical-text"};
const sizes: Record<Size,string>={sm:"h-8 px-3 text-xs",md:"h-10 px-4 text-sm",lg:"h-12 px-5 text-base"};
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>{variant?:Variant;size?:Size;iconBefore?:ReactNode;iconAfter?:ReactNode;loading?:boolean;loadingLabel?:string;fullWidth?:boolean}
export function Button({variant="primary",size="md",iconBefore,iconAfter,loading=false,loadingLabel="Loading",fullWidth=false,disabled: isDisabled,children,className,type="button",...props}:ButtonProps){
 return <button type={type} disabled={isDisabled||loading} aria-busy={loading||undefined} className={cn("inline-flex items-center justify-center gap-2 rounded-md border font-medium",focusRing,transition,disabled,sizes[size],variants[variant],fullWidth&&"w-full",className)} {...props}>{loading?<span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent motion-reduce:animate-none"/>:iconBefore}<span>{loading?loadingLabel:children}</span>{!loading&&iconAfter}</button>;
}
