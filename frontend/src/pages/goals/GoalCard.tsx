import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/formatters";
import type { Goal } from "@/api/types";

const statusVariants: Record<string, "success" | "warning" | "default" | "info"> = {
  active: "success",
  paused: "warning",
  completed: "default",
  archived: "default",
};

interface GoalCardProps {
  goal: Goal;
  onClick: () => void;
}

export function GoalCard({ goal, onClick }: GoalCardProps) {
  return (
    <Card interactive className="p-4" onClick={onClick}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-[14px] font-semibold text-[var(--color-text-primary)]">
          {goal.name}
        </h3>
        <Badge variant={statusVariants[goal.status] ?? "default"}>
          {goal.status}
        </Badge>
      </div>

      <div className="text-[12px] text-[var(--color-text-secondary)] mb-3">
        {formatDate(goal.start_date)}
        {goal.end_date ? ` \u2014 ${formatDate(goal.end_date)}` : " \u2014 ongoing"}
      </div>

      {goal.metrics.length > 0 && (
        <div className="text-[12px] text-[var(--color-text-secondary)] mb-1">
          <span className="text-[var(--color-text-tertiary)]">Metrics:</span>{" "}
          {goal.metrics.join(", ")}
        </div>
      )}

      <div className="text-[12px] text-[var(--color-text-tertiary)]">
        Review every {goal.review_cadence_days} day
        {goal.review_cadence_days !== 1 ? "s" : ""}
      </div>
    </Card>
  );
}
