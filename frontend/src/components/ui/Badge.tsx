import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const variants = {
  default:
    "bg-[var(--color-surface-tertiary)] text-[var(--color-text-secondary)]",
  success:
    "bg-[var(--color-success-muted)] text-[var(--color-success)] border border-[var(--color-success-muted-border)]",
  warning:
    "bg-[var(--color-warning-muted)] text-[var(--color-warning)] border border-[var(--color-warning-muted-border)]",
  danger:
    "bg-[var(--color-danger-muted)] text-[var(--color-danger)] border border-[var(--color-danger-muted-border)]",
  info: "bg-[var(--color-info-muted)] text-[var(--color-info)] border border-[var(--color-info-muted-border)]",
  outline:
    "bg-transparent border border-[var(--color-border-default)] text-[var(--color-text-secondary)]",
};

interface BadgeProps {
  variant?: keyof typeof variants;
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function Badge({
  variant = "default",
  children,
  className,
  style,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-0.5 text-[11px] font-medium rounded-full whitespace-nowrap",
        variants[variant],
        className,
      )}
      style={style}
    >
      {children}
    </span>
  );
}
