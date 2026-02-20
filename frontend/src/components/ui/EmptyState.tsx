import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-4 text-center",
        className,
      )}
    >
      <Icon className="h-10 w-10 text-[var(--color-text-placeholder)] mb-3" />
      <h3 className="text-[15px] font-medium text-[var(--color-text-primary)] mb-1">
        {title}
      </h3>
      {description && (
        <p className="text-[13px] text-[var(--color-text-secondary)] mb-4 max-w-xs">
          {description}
        </p>
      )}
      {action}
    </div>
  );
}
