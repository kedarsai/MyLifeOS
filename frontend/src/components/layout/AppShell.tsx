import { useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { CommandPalette } from "@/components/CommandPalette";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [cmdOpen, setCmdOpen] = useState(false);

  return (
    <div className="h-screen w-full flex bg-[var(--color-canvas)]">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header onOpenCommandPalette={() => setCmdOpen(true)} />
        <main className="flex-1 overflow-y-auto scrollbar p-6">
          {children}
        </main>
      </div>
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  );
}
