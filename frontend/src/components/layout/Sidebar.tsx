import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/cn";
import { NAV_GROUPS } from "@/lib/constants";

const STORAGE_KEY = "lifeos-sidebar";

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) === "collapsed";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "b") {
        e.preventDefault();
        setCollapsed((c) => !c);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  return (
    <aside
      className={cn(
        "h-screen flex flex-col bg-[var(--color-sidebar-bg)] transition-[width] duration-200 shrink-0 overflow-hidden",
        collapsed ? "w-12" : "w-60",
      )}
    >
      {/* Brand */}
      <div className="px-3 pt-4 pb-2">
        {collapsed ? (
          <div className="flex justify-center">
            <span className="text-[15px] font-bold text-[var(--color-sidebar-text-active)]">
              L
            </span>
          </div>
        ) : (
          <>
            <h2 className="text-[15px] font-bold text-[var(--color-sidebar-text-active)]">
              LifeOS
            </h2>
            <p className="text-[11px] text-[var(--color-sidebar-text-muted)] mt-0.5">
              Local-first assistant
            </p>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mb-3">
            {!collapsed && (
              <div className="px-2 py-1 text-[11px] uppercase tracking-widest font-semibold text-[var(--color-sidebar-section)]">
                {group.label}
              </div>
            )}
            {group.items.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md text-[13px] transition-colors",
                    collapsed
                      ? "justify-center px-0 py-2"
                      : "px-2.5 py-1.5",
                    isActive
                      ? "bg-[var(--color-sidebar-bg-active)] text-[var(--color-sidebar-text-active)] font-medium"
                      : "text-[var(--color-sidebar-text)] hover:bg-[var(--color-sidebar-bg-hover)]",
                  )
                }
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-center py-3 border-t border-[var(--color-sidebar-border)] text-[var(--color-sidebar-text-muted)] hover:text-[var(--color-sidebar-text)] transition-colors cursor-pointer"
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>
    </aside>
  );
}
