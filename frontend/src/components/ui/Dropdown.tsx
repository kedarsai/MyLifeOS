import { useState, useEffect, useRef, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

interface DropdownItem {
  label: string;
  onClick: () => void;
  icon?: LucideIcon;
  danger?: boolean;
}

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: "left" | "right";
}

export function Dropdown({ trigger, items, align = "right" }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", keyHandler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", keyHandler);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            "absolute z-50 mt-1 min-w-[160px] py-1",
            "bg-[var(--color-surface-primary)] border border-[var(--color-border-default)] rounded-lg shadow-lg",
            "animate-[dropdown-in_100ms_ease-out]",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {items.map((item) => (
            <button
              key={item.label}
              onClick={() => {
                item.onClick();
                setOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-left rounded-md cursor-pointer",
                item.danger
                  ? "text-[var(--color-danger)] hover:bg-[var(--color-danger-muted)]"
                  : "text-[var(--color-text-primary)] hover:bg-[var(--color-layer-hover)]",
              )}
            >
              {item.icon && <item.icon className="h-4 w-4" />}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
