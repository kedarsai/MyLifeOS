import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ label, error, className, id, ...props }, ref) {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[13px] font-medium text-[var(--color-text-primary)]"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={cn(
            "min-h-[100px] px-3 py-2 text-[13px] rounded-md resize-y",
            "bg-[var(--color-input-bg)] border border-[var(--color-input-border)]",
            "text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)]",
            "focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent",
            error && "border-[var(--color-danger)]",
            className,
          )}
          {...props}
        />
        {error && (
          <p className="text-[11px] text-[var(--color-danger)]">{error}</p>
        )}
      </div>
    );
  },
);
