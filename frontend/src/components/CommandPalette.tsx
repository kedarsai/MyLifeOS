import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { createPortal } from "react-dom";
import { Search } from "lucide-react";
import { cn } from "@/lib/cn";
import { NAV_GROUPS } from "@/lib/constants";
import { useDebounce } from "@/hooks/useDebounce";
import { useSearch } from "@/api/hooks/useSearch";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

const allNavItems = NAV_GROUPS.flatMap((g) =>
  g.items.map((item) => ({ ...item, group: g.label })),
);

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const overlayRef = useRef<HTMLDivElement>(null);

  const { data: searchResults } = useSearch({ q: debouncedQuery, page_size: 5 });

  // Keyboard shortcut to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (open) onClose();
        // Parent handles opening
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  if (!open) return null;

  // Filter nav items by query
  const filteredNav = query
    ? allNavItems.filter(
        (item) =>
          item.label.toLowerCase().includes(query.toLowerCase()) ||
          item.path.toLowerCase().includes(query.toLowerCase()),
      )
    : allNavItems;

  const navResults = filteredNav.map((item) => ({
    type: "nav" as const,
    label: item.label,
    description: `Go to ${item.label}`,
    path: item.path,
    icon: item.icon,
  }));

  const entryResults = (searchResults?.items ?? []).map((item) => ({
    type: "entry" as const,
    label: item.summary || item.raw_text.slice(0, 80),
    description: `${item.type} - ${item.status}`,
    path: `/timeline?q=${encodeURIComponent(item.summary || "")}`,
  }));

  const allResults = [...navResults, ...entryResults];

  const handleSelect = (idx: number) => {
    const result = allResults[idx];
    if (result) {
      navigate(result.path);
      onClose();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, allResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect(selectedIndex);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return createPortal(
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/40 dark:bg-black/60 backdrop-blur-[2px]"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="w-full max-w-[560px] mx-4 bg-[var(--color-surface-primary)] rounded-xl shadow-overlay overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border-subtle)]">
          <Search className="h-4 w-4 text-[var(--color-text-tertiary)] shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search pages, entries..."
            className="flex-1 bg-transparent text-[14px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] outline-none"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-tertiary)] text-[var(--color-text-tertiary)] border border-[var(--color-border-default)]">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[320px] overflow-y-auto scrollbar py-1">
          {allResults.length === 0 && (
            <div className="px-4 py-8 text-center text-[13px] text-[var(--color-text-tertiary)]">
              No results found
            </div>
          )}
          {allResults.map((result, i) => (
            <button
              key={`${result.type}-${result.label}-${i}`}
              onClick={() => handleSelect(i)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-2 text-left cursor-pointer transition-colors",
                i === selectedIndex
                  ? "bg-[var(--color-layer-hover)]"
                  : "hover:bg-[var(--color-layer-hover)]",
              )}
            >
              {"icon" in result && result.icon && (
                <result.icon className="h-4 w-4 text-[var(--color-text-tertiary)] shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <div className="text-[13px] text-[var(--color-text-primary)] truncate">
                  {result.label}
                </div>
                <div className="text-[11px] text-[var(--color-text-tertiary)] truncate">
                  {result.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>,
    document.body,
  );
}
