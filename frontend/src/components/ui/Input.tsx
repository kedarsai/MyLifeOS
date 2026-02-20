import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className, id, ...props },
  ref,
) {
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
      <input
        ref={ref}
        id={inputId}
        className={cn(
          "h-8 px-3 text-[13px] rounded-md",
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
});
