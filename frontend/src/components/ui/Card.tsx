import type { ReactNode, HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  interactive?: boolean;
}

export function Card({
  children,
  interactive = false,
  className,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "bg-[var(--color-surface-primary)] border-[0.5px] border-[var(--color-border-subtle)] rounded-lg",
        interactive &&
          "cursor-pointer hover:shadow-md hover:border-[var(--color-border-default)] transition-all duration-150",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
