import { cn } from "@/lib/cn";

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  className?: string;
}

export function Toggle({ checked, onChange, label, className }: ToggleProps) {
  return (
    <label
      className={cn("inline-flex items-center gap-2 cursor-pointer", className)}
    >
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors duration-200 cursor-pointer",
          checked
            ? "bg-[var(--color-accent)]"
            : "bg-[var(--color-border-default)]",
        )}
      >
        <span
          className={cn(
            "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transform transition-transform duration-200 mt-0.5",
            checked ? "translate-x-[18px] ml-0" : "translate-x-0.5",
          )}
        />
      </button>
      {label && (
        <span className="text-[13px] text-[var(--color-text-secondary)]">
          {label}
        </span>
      )}
    </label>
  );
}
