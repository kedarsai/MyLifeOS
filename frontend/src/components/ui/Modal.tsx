import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

const sizeClasses = {
  sm: "max-w-[400px]",
  md: "max-w-[560px]",
  lg: "max-w-[720px]",
};

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: keyof typeof sizeClasses;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal({
  open,
  onClose,
  title,
  size = "md",
  children,
  footer,
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-[2px]"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div
        className={cn(
          "w-full mx-4 bg-[var(--color-surface-primary)] rounded-xl shadow-overlay",
          "animate-[modal-in_200ms_ease-out]",
          sizeClasses[size],
        )}
        role="dialog"
        aria-modal
      >
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-subtle)]">
            <h2 className="text-[15px] font-semibold text-[var(--color-text-primary)]">
              {title}
            </h2>
            <button
              onClick={onClose}
              className="p-1 rounded-md hover:bg-[var(--color-layer-hover)] text-[var(--color-text-tertiary)] transition-colors cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        <div className="px-6 py-4">{children}</div>
        {footer && (
          <div className="px-6 py-3 border-t border-[var(--color-border-subtle)] flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
