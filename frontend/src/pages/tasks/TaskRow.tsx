import { CheckCircle, MoreHorizontal, Trash2, FolderOpen } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Dropdown } from "@/components/ui/Dropdown";
import { useCompleteTask, useDeleteTask } from "@/api/hooks/useTasks";
import { formatDate } from "@/lib/formatters";
import type { Task } from "@/api/types";

const priorityColors: Record<string, string> = {
  high: "bg-[var(--color-priority-high)]",
  medium: "bg-[var(--color-priority-medium)]",
  low: "bg-[var(--color-priority-low)]",
};

const statusVariants: Record<string, "info" | "warning" | "success" | "default"> = {
  open: "info",
  in_progress: "warning",
  done: "success",
  cancelled: "default",
};

function isOverdue(dueDate: string | null): boolean {
  if (!dueDate) return false;
  return new Date(dueDate) < new Date(new Date().toDateString());
}

interface TaskRowProps {
  task: Task;
}

export function TaskRow({ task }: TaskRowProps) {
  const completeTask = useCompleteTask();
  const deleteTask = useDeleteTask();

  return (
    <>
      {/* Title */}
      <td className="py-2 px-2.5 text-[13px]">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[var(--color-text-primary)]">
            {task.title}
          </span>
          <Badge variant={statusVariants[task.status] ?? "default"}>
            {task.status.replace("_", " ")}
          </Badge>
        </div>
      </td>

      {/* Due date */}
      <td className="py-2 px-2.5 text-[13px]">
        {task.due_date ? (
          <span
            className={
              isOverdue(task.due_date)
                ? "text-[var(--color-danger)] font-medium"
                : "text-[var(--color-text-secondary)]"
            }
          >
            {formatDate(task.due_date)}
            {isOverdue(task.due_date) && (
              <Badge variant="danger" className="ml-1.5">
                Overdue
              </Badge>
            )}
          </span>
        ) : (
          <span className="text-[var(--color-text-tertiary)]">&mdash;</span>
        )}
      </td>

      {/* Priority dot */}
      <td className="py-2 px-2.5">
        <span
          className={`inline-block w-2 h-2 rounded-full ${priorityColors[task.priority] ?? ""}`}
          title={task.priority}
        />
      </td>

      {/* Goal */}
      <td className="py-2 px-2.5 text-[13px]">
        {task.goal_name ? (
          <Badge variant="outline">{task.goal_name}</Badge>
        ) : (
          <span className="text-[var(--color-text-tertiary)]">&mdash;</span>
        )}
      </td>

      {/* Project */}
      <td className="py-2 px-2.5 text-[13px]">
        {task.project_name ? (
          <Badge variant="outline">{task.project_name}</Badge>
        ) : (
          <span className="text-[var(--color-text-tertiary)]">&mdash;</span>
        )}
      </td>

      {/* Actions */}
      <td className="py-2 px-2.5 text-right">
        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {task.status !== "done" && task.status !== "cancelled" && (
            <button
              onClick={() => completeTask.mutate(task.task_id)}
              className="p-1 rounded hover:bg-[var(--color-success-muted)] text-[var(--color-success)] cursor-pointer"
              title="Complete"
            >
              <CheckCircle className="h-4 w-4" />
            </button>
          )}
          <Dropdown
            trigger={
              <button className="p-1 rounded hover:bg-[var(--color-layer-hover)] text-[var(--color-text-tertiary)] cursor-pointer">
                <MoreHorizontal className="h-4 w-4" />
              </button>
            }
            items={[
              {
                label: "Assign Project",
                icon: FolderOpen,
                onClick: () => {
                  /* TODO: project assignment modal */
                },
              },
              {
                label: "Delete",
                icon: Trash2,
                danger: true,
                onClick: () => deleteTask.mutate(task.task_id),
              },
            ]}
          />
        </div>
      </td>
    </>
  );
}
