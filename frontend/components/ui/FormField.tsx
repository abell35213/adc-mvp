import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, ReactNode } from "react";
import { cloneElement, isValidElement } from "react";
import { cn } from "@/lib/design/utilities";
import { designTokens } from "@/lib/design/tokens";

export function FormField({
  id,
  label,
  required,
  helpText,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  helpText?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}) {
  const controlId = isValidElement(children) ? ((children.props as any).id ?? id) : id;
  const helpId = helpText ? `${controlId}-help` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;

  const control = isValidElement(children)
    ? cloneElement(children as any, {
        id: controlId,
        "aria-describedby": [((children.props as any)["aria-describedby"] as string | undefined), describedBy]
          .filter(Boolean)
          .join(" ") || undefined,
        "aria-invalid": error ? true : (children.props as any)["aria-invalid"],
        required: required ?? (children.props as any).required,
      })
    : children;

  return (
    <div className="space-y-1.5">
      <label htmlFor={controlId} className="text-sm font-medium text-text-secondary">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {control}
      {helpText && (
        <p id={helpId} className="text-xs text-text-muted">
          {helpText}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-status-critical-text">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={cn(
        designTokens.control.input,
        "w-full",
        props["aria-invalid"] && "border-status-critical-border",
        props.className,
      )}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(designTokens.control.input, "w-full", props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(designTokens.control.input, "min-h-24 w-full", props.className)} />;
}
