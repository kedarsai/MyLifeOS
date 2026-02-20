import { lazy, Suspense, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Spinner } from "@/components/ui/Spinner";

// Lazy-loaded pages
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"));
const TodayPage = lazy(() => import("@/pages/today/TodayPage"));
const TasksPage = lazy(() => import("@/pages/tasks/TasksPage"));
const GoalsPage = lazy(() => import("@/pages/goals/GoalsPage"));
const ProjectsPage = lazy(() => import("@/pages/projects/ProjectsPage"));
const CapturePage = lazy(() => import("@/pages/capture/CapturePage"));
const InboxPage = lazy(() => import("@/pages/inbox/InboxPage"));
const TimelinePage = lazy(() => import("@/pages/timeline/TimelinePage"));
const ChatPage = lazy(() => import("@/pages/chat/ChatPage"));
const ImprovementsPage = lazy(
  () => import("@/pages/improvements/ImprovementsPage"),
);
const ReviewsPage = lazy(() => import("@/pages/reviews/ReviewsPage"));
const RemindersPage = lazy(() => import("@/pages/reminders/RemindersPage"));
const PromptsPage = lazy(() => import("@/pages/prompts/PromptsPage"));
const RunsPage = lazy(() => import("@/pages/runs/RunsPage"));
const ConflictsPage = lazy(() => import("@/pages/conflicts/ConflictsPage"));
const SearchPage = lazy(() => import("@/pages/search/SearchPage"));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spinner size="lg" />
    </div>
  );
}

// Open command palette from keyboard
function GlobalKeyboardHandler() {
  const location = useLocation();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        // Dispatch custom event for CommandPalette
        document.dispatchEvent(new CustomEvent("open-command-palette"));
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [location]);

  return null;
}

export function App() {
  return (
    <>
      <GlobalKeyboardHandler />
      <AppShell>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/today" element={<TodayPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/goals" element={<GoalsPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/capture" element={<CapturePage />} />
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/timeline" element={<TimelinePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/improvements" element={<ImprovementsPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/reminders" element={<RemindersPage />} />
            <Route path="/prompts" element={<PromptsPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/conflicts" element={<ConflictsPage />} />
            <Route path="/search" element={<SearchPage />} />
          </Routes>
        </Suspense>
      </AppShell>
    </>
  );
}
