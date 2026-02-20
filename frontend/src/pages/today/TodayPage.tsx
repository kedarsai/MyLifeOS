import { Sun, CheckCircle } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToday, useCompleteTask } from "@/api/hooks/useTasks";
import { formatDate } from "@/lib/formatters";
import type { Task } from "@/api/types";

const priorityColors: Record<string, string> = {
  high: "bg-[var(--color-priority-high)]",
  medium: "bg-[var(--color-priority-medium)]",
  low: "bg-[var(--color-priority-low)]",
};

function TaskItem({ task }: { task: Task }) {
  const completeTask = useCompleteTask();

  return (
    <div className="group flex items-center gap-3 py-2 px-3 hover:bg-[var(--color-layer-hover)] rounded-md transition-colors">
      <button
        onClick={() => completeTask.mutate(task.task_id)}
        className="shrink-0 p-0.5 rounded hover:bg-[var(--color-success-muted)] text-[var(--color-text-tertiary)] hover:text-[var(--color-success)] transition-colors cursor-pointer"
      >
        <CheckCircle className="h-4 w-4" />
      </button>
      <span
        className={`w-2 h-2 rounded-full shrink-0 ${priorityColors[task.priority] ?? ""}`}
      />
      <span className="text-[13px] text-[var(--color-text-primary)] flex-1 min-w-0 truncate">
        {task.title}
      </span>
      {task.due_date && (
        <span className="text-[11px] text-[var(--color-text-tertiary)] shrink-0">
          {formatDate(task.due_date)}
        </span>
      )}
      {task.goal_name && (
        <Badge variant="outline" className="shrink-0">
          {task.goal_name}
        </Badge>
      )}
    </div>
  );
}

function TaskSection({
  title,
  tasks,
  variant = "default",
}: {
  title: string;
  tasks: Task[];
  variant?: "danger" | "warning" | "default";
}) {
  if (tasks.length === 0) return null;

  const headerColor =
    variant === "danger"
      ? "text-[var(--color-danger)]"
      : variant === "warning"
        ? "text-[var(--color-warning)]"
        : "text-[var(--color-text-tertiary)]";

  return (
    <div className="mb-6">
      <h3
        className={`text-[12px] font-semibold uppercase tracking-wider ${headerColor} mb-2 px-3`}
      >
        {title} ({tasks.length})
      </h3>
      <div className="flex flex-col">
        {tasks.map((task) => (
          <TaskItem key={task.task_id} task={task} />
        ))}
      </div>
    </div>
  );
}

export default function TodayPage() {
  const { data, isLoading, error } = useToday();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-[13px] text-[var(--color-danger)] py-4">
        Failed to load today: {error.message}
      </div>
    );
  }

  if (!data) return null;

  const totalTasks =
    data.overdue.length + data.due_today.length + data.next_actions.length;

  return (
    <div>
      <PageHeader
        title="Today"
        description={data.today}
      />

      {totalTasks === 0 ? (
        <EmptyState
          icon={Sun}
          title="All clear!"
          description="No tasks due today. Enjoy your day."
        />
      ) : (
        <>
          <TaskSection
            title="Overdue"
            tasks={data.overdue}
            variant="danger"
          />
          <TaskSection
            title="Due Today"
            tasks={data.due_today}
            variant="warning"
          />
          <TaskSection title="Next Actions" tasks={data.next_actions} />
        </>
      )}
    </div>
  );
}
