import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckSquare, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Table } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { TaskFilters } from "./TaskFilters";
import { TaskRow } from "./TaskRow";
import { TaskCreateModal } from "./TaskCreateModal";
import { useTasks } from "@/api/hooks/useTasks";

export default function TasksPage() {
  const [searchParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);

  const filters = {
    status: searchParams.get("status") ?? undefined,
    goal_id: searchParams.get("goal_id") ?? undefined,
    project_id: searchParams.get("project_id") ?? undefined,
    q: searchParams.get("q") ?? undefined,
    include_done: searchParams.get("include_done") === "1",
  };

  const { data, isLoading, error } = useTasks(filters);

  return (
    <div>
      <PageHeader
        title="Tasks"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Create Task
          </Button>
        }
      />

      <TaskFilters value={filters} />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load tasks: {error.message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={CheckSquare}
          title="No tasks found"
          description="Try adjusting your filters or create a new task."
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-3.5 w-3.5" />
              Create Task
            </Button>
          }
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <Table>
            <Table.Head>
              <Table.Row>
                <Table.HeadCell>Title</Table.HeadCell>
                <Table.HeadCell>Due Date</Table.HeadCell>
                <Table.HeadCell className="w-8">P</Table.HeadCell>
                <Table.HeadCell>Goal</Table.HeadCell>
                <Table.HeadCell>Project</Table.HeadCell>
                <Table.HeadCell className="w-20 text-right">
                  Actions
                </Table.HeadCell>
              </Table.Row>
            </Table.Head>
            <Table.Body>
              {data.items.map((task) => (
                <Table.Row key={task.task_id}>
                  <TaskRow task={task} />
                </Table.Row>
              ))}
            </Table.Body>
          </Table>

          <div className="mt-3 text-[12px] text-[var(--color-text-tertiary)]">
            {data.total} task{data.total !== 1 ? "s" : ""}
          </div>
        </>
      )}

      <TaskCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  );
}
