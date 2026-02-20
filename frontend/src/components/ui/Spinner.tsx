import { cn } from "@/lib/cn";

const sizes = {
  sm: "h-4 w-4 border-[1.5px]",
  md: "h-6 w-6 border-2",
  lg: "h-8 w-8 border-2",
};

interface SpinnerProps {
  size?: keyof typeof sizes;
  className?: string;
}

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-[var(--color-accent)] border-t-transparent",
        sizes[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
