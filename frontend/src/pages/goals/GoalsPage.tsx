import { useState } from "react";
import { Star, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { GoalCard } from "./GoalCard";
import { GoalCreateModal } from "./GoalCreateModal";
import { GoalDashboardPanel } from "./GoalDashboard";
import { useGoals } from "@/api/hooks/useGoals";

export default function GoalsPage() {
  const { data, isLoading, error } = useGoals();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);

  return (
    <div>
      <PageHeader
        title="Goals"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Goal
          </Button>
        }
      />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load goals: {error.message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={Star}
          title="No goals yet"
          description="Create your first goal to start tracking progress."
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              Create Goal
            </Button>
          }
        />
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
          {data.items.map((goal) => (
            <GoalCard
              key={goal.goal_id}
              goal={goal}
              onClick={() =>
                setSelectedGoalId(
                  selectedGoalId === goal.goal_id ? null : goal.goal_id,
                )
              }
            />
          ))}
        </div>
      )}

      {selectedGoalId && (
        <div className="mt-4">
          <GoalDashboardPanel
            goalId={selectedGoalId}
            onClose={() => setSelectedGoalId(null)}
          />
        </div>
      )}

      <GoalCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  );
}
