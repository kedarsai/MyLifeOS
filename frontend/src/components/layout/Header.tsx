import { useLocation } from "react-router-dom";
import { Search, Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { NAV_GROUPS } from "@/lib/constants";

function getPageTitle(pathname: string): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (pathname.startsWith(item.path)) return item.label;
    }
  }
  return "LifeOS";
}

interface HeaderProps {
  onOpenCommandPalette: () => void;
}

export function Header({ onOpenCommandPalette }: HeaderProps) {
  const location = useLocation();
  const { theme, setTheme } = useTheme();

  const title = getPageTitle(location.pathname);

  const themeIcon =
    theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  const ThemeIcon = themeIcon;

  const cycleTheme = () => {
    if (theme === "light") setTheme("dark");
    else if (theme === "dark") setTheme("system");
    else setTheme("light");
  };

  return (
    <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-[var(--color-border-subtle)] bg-[var(--color-surface-primary)]">
      <h1 className="text-[15px] font-semibold text-[var(--color-text-primary)]">
        {title}
      </h1>
      <div className="flex items-center gap-1">
        {/* Search trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[12px] text-[var(--color-text-tertiary)] bg-[var(--color-surface-tertiary)] hover:bg-[var(--color-layer-hover)] transition-colors cursor-pointer"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search...</span>
          <kbd className="hidden sm:inline text-[10px] px-1 py-0.5 rounded bg-[var(--color-surface-primary)] border border-[var(--color-border-default)]">
            {"\u2318"}K
          </kbd>
        </button>

        {/* Theme toggle */}
        <button
          onClick={cycleTheme}
          className="h-7 w-7 flex items-center justify-center rounded-md text-[var(--color-text-tertiary)] hover:bg-[var(--color-layer-hover)] transition-colors cursor-pointer"
          title={`Theme: ${theme}`}
        >
          <ThemeIcon className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
