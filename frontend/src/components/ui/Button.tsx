import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

const variants = {
  primary:
    "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)]",
  secondary:
    "bg-[var(--color-surface-primary)] border border-[var(--color-border-default)] text-[var(--color-text-primary)] hover:bg-[var(--color-layer-hover)]",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]",
  danger: "bg-[var(--color-danger)] text-white hover:opacity-90",
};

const sizes = {
  sm: "h-7 px-2.5 text-[11px]",
  md: "h-8 px-3 text-[13px]",
  lg: "h-9 px-4 text-[13px]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      className,
      children,
      ...props
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-150 focus-ring cursor-pointer",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      >
        {loading && <Spinner size="sm" />}
        {children}
      </button>
    );
  },
);
