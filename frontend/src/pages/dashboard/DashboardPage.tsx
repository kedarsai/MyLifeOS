import { Link } from "react-router-dom";
import {
  Inbox,
  CheckSquare,
  AlertTriangle,
  MessageSquare,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { useDashboard } from "@/api/hooks/useDashboard";
import { timeAgo, truncate } from "@/lib/formatters";

function StatCard({
  label,
  value,
  icon: Icon,
  href,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  href: string;
}) {
  return (
    <Link to={href}>
      <Card interactive className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[22px] font-bold text-[var(--color-text-primary)]">
              {value}
            </p>
            <p className="text-[12px] text-[var(--color-text-secondary)] mt-0.5">
              {label}
            </p>
          </div>
          <Icon className="h-5 w-5 text-[var(--color-text-tertiary)]" />
        </div>
      </Card>
    </Link>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-[13px] text-[var(--color-danger)] py-4">
        Failed to load dashboard: {error?.message ?? "Unknown error"}
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Dashboard" />

      {/* Stat grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Inbox"
          value={data.entries.inbox}
          icon={Inbox}
          href="/inbox"
        />
        <StatCard
          label="Tasks Due"
          value={data.tasks_due}
          icon={CheckSquare}
          href="/tasks"
        />
        <StatCard
          label="Open Thoughts"
          value={data.open_thoughts}
          icon={MessageSquare}
          href="/timeline?type=thought"
        />
        <StatCard
          label="Conflicts"
          value={data.conflicts.open}
          icon={AlertTriangle}
          href="/conflicts"
        />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent entries */}
        <Card className="p-4">
          <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)] mb-3">
            Recent Entries
          </h3>
          {data.recent_entries.length === 0 ? (
            <p className="text-[12px] text-[var(--color-text-tertiary)]">
              No entries yet
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {data.recent_entries.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center gap-2 py-1.5 border-b border-[var(--color-border-subtle)] last:border-0"
                >
                  <Badge
                    className="capitalize shrink-0"
                    style={{
                      backgroundColor: `var(--color-type-${entry.type}-bg)`,
                      color: `var(--color-type-${entry.type}-text)`,
                    }}
                  >
                    {entry.type}
                  </Badge>
                  <span className="text-[13px] text-[var(--color-text-primary)] truncate flex-1">
                    {entry.summary || truncate(entry.raw_text, 60)}
                  </span>
                  <span className="text-[11px] text-[var(--color-text-tertiary)] shrink-0">
                    {timeAgo(entry.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Recent runs */}
        <Card className="p-4">
          <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)] mb-3">
            Recent Runs
          </h3>
          {data.recent_runs.length === 0 ? (
            <p className="text-[12px] text-[var(--color-text-tertiary)]">
              No runs yet
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {data.recent_runs.map((run) => (
                <div
                  key={run.run_id}
                  className="flex items-center gap-2 py-1.5 border-b border-[var(--color-border-subtle)] last:border-0"
                >
                  <Badge
                    variant={
                      run.status === "success"
                        ? "success"
                        : run.status === "failed"
                          ? "danger"
                          : "warning"
                    }
                  >
                    {run.status}
                  </Badge>
                  <span className="text-[13px] text-[var(--color-text-primary)] truncate flex-1">
                    {run.prompt_id}
                  </span>
                  <span className="text-[11px] text-[var(--color-text-tertiary)] shrink-0">
                    {timeAgo(run.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
