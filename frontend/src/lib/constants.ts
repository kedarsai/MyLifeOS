import {
  LayoutDashboard,
  Sun,
  CheckSquare,
  Star,
  Settings,
  PenTool,
  Inbox,
  ArrowRight,
  MessageSquare,
  TrendingUp,
  BarChart2,
  Clock,
  Zap,
  Play,
  AlertTriangle,
} from "lucide-react";

export const NAV_GROUPS = [
  {
    label: "Core",
    items: [
      { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { path: "/today", label: "Today", icon: Sun },
      { path: "/tasks", label: "Tasks", icon: CheckSquare },
      { path: "/goals", label: "Goals", icon: Star },
      { path: "/projects", label: "Projects", icon: Settings },
    ],
  },
  {
    label: "Capture",
    items: [
      { path: "/capture", label: "Capture", icon: PenTool },
      { path: "/inbox", label: "Inbox", icon: Inbox },
      { path: "/timeline", label: "Timeline", icon: ArrowRight },
    ],
  },
  {
    label: "Coach",
    items: [
      { path: "/chat", label: "Chat", icon: MessageSquare },
      { path: "/improvements", label: "Improvements", icon: TrendingUp },
      { path: "/reviews", label: "Reviews", icon: BarChart2 },
      { path: "/reminders", label: "Reminders", icon: Clock },
    ],
  },
  {
    label: "System",
    items: [
      { path: "/prompts", label: "Prompts", icon: Zap },
      { path: "/runs", label: "Runs", icon: Play },
      { path: "/conflicts", label: "Conflicts", icon: AlertTriangle },
    ],
  },
] as const;

export const ENTRY_TYPES = [
  "activity",
  "sleep",
  "food",
  "thought",
  "idea",
  "todo",
  "goal",
  "note",
  "chat",
] as const;

export type EntryType = (typeof ENTRY_TYPES)[number];
