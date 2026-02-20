import { forwardRef, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select(
    { label, error, options, placeholder, className, id, ...props },
    ref,
  ) {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="text-[13px] font-medium text-[var(--color-text-primary)]"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              "h-8 w-full appearance-none px-3 pr-8 text-[13px] rounded-md",
              "bg-[var(--color-input-bg)] border border-[var(--color-input-border)]",
              "text-[var(--color-text-primary)]",
              "focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent",
              error && "border-[var(--color-danger)]",
              className,
            )}
            {...props}
          >
            {placeholder && <option value="">{placeholder}</option>}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-tertiary)]" />
        </div>
        {error && (
          <p className="text-[11px] text-[var(--color-danger)]">{error}</p>
        )}
      </div>
    );
  },
);
