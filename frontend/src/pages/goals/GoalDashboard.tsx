import { MessageSquare } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { useGoalDashboard } from "@/api/hooks/useGoals";
import { formatDate } from "@/lib/formatters";

interface GoalDashboardProps {
  goalId: string;
  onClose: () => void;
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-[18px] font-semibold text-[var(--color-text-primary)]">
        {value}
      </div>
      <div className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5">
        {label}
      </div>
    </div>
  );
}

export function GoalDashboardPanel({ goalId, onClose }: GoalDashboardProps) {
  const navigate = useNavigate();
  const { data, isLoading, error } = useGoalDashboard(goalId);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="p-6">
        <div className="text-[13px] text-[var(--color-danger)]">
          Failed to load dashboard
        </div>
      </Card>
    );
  }

  const { goal, metrics, latest_review } = data;

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-[15px] font-semibold text-[var(--color-text-primary)]">
            {goal.name}
          </h3>
          <p className="text-[12px] text-[var(--color-text-secondary)] mt-0.5">
            {formatDate(goal.start_date)}
            {goal.end_date ? ` \u2014 ${formatDate(goal.end_date)}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/chat?entity_type=goal&entity_id=${goalId}`)}
          >
            <MessageSquare className="h-3.5 w-3.5 mr-1" />
            Chat
          </Button>
          <button
            onClick={onClose}
            className="text-[12px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-3 gap-4 py-4 border-y border-[var(--color-border-subtle)]">
        <StatItem
          label="Steps Avg (7d)"
          value={
            metrics.steps_avg_7d != null
              ? Math.round(metrics.steps_avg_7d).toLocaleString()
              : "\u2014"
          }
        />
        <StatItem
          label="Step Streak"
          value={`${metrics.step_streak_days}d`}
        />
        <StatItem
          label="Sleep Avg (7d)"
          value={
            metrics.sleep_avg_min_7d != null
              ? `${Math.round(metrics.sleep_avg_min_7d / 60)}h ${Math.round(metrics.sleep_avg_min_7d % 60)}m`
              : "\u2014"
          }
        />
        <StatItem
          label="Weight Trend (30d)"
          value={
            metrics.weight_trend_kg_30d != null
              ? `${metrics.weight_trend_kg_30d > 0 ? "+" : ""}${metrics.weight_trend_kg_30d.toFixed(1)} kg`
              : "\u2014"
          }
        />
        <StatItem
          label="Logging"
          value={`${metrics.logging_completeness_7d_pct}%`}
        />
        <StatItem
          label="Linked Entries"
          value={String(metrics.linked_entries)}
        />
      </div>

      {/* Latest review */}
      {latest_review && (
        <div className="mt-4">
          <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-2">
            Latest Review
          </h4>
          <div className="text-[12px] text-[var(--color-text-secondary)]">
            {formatDate(latest_review.week_start)} &mdash;{" "}
            {formatDate(latest_review.week_end)}
          </div>
          <pre className="mt-2 text-[12px] text-[var(--color-text-secondary)] bg-[var(--color-surface-tertiary)] rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(latest_review.review, null, 2)}
          </pre>
        </div>
      )}
    </Card>
  );
}
