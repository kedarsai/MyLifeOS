import { useState } from "react";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/lib/cn";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { timeAgo } from "@/lib/formatters";
import type { PromptRun } from "@/api/types";

const statusVariants: Record<string, "success" | "danger" | "warning"> = {
  success: "success",
  failed: "danger",
  pending: "warning",
};

export default function RunsPage() {
  const { data, isLoading, error } = useQuery<{
    items: PromptRun[];
    total: number;
  }>({
    queryKey: ["runs"],
    queryFn: () => apiFetch("/runs"),
  });

  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const { data: runDetail } = useQuery({
    queryKey: ["runs", selectedRun],
    queryFn: () => apiFetch<Record<string, unknown>>(`/runs/${selectedRun}`),
    enabled: !!selectedRun,
  });

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Runs" />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load runs: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={Play}
          title="No runs yet"
          description="Prompt runs will appear here after processing."
        />
      )}

      {data && data.items.length > 0 && (
        <div className="flex flex-1 gap-4 min-h-0">
          {/* Run list */}
          <div className="w-80 shrink-0 overflow-y-auto scrollbar flex flex-col gap-1">
            {data.items.map((run) => (
              <button
                key={run.run_id}
                onClick={() => setSelectedRun(run.run_id)}
                className={cn(
                  "text-left px-3 py-2 rounded-md transition-colors cursor-pointer",
                  selectedRun === run.run_id
                    ? "bg-[var(--color-layer-active)]"
                    : "hover:bg-[var(--color-layer-hover)]",
                )}
              >
                <div className="flex items-center gap-2">
                  <Badge variant={statusVariants[run.status] ?? "default"}>
                    {run.status}
                  </Badge>
                  <span className="text-[13px] text-[var(--color-text-primary)] truncate">
                    {run.prompt_id}
                  </span>
                </div>
                <div className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5">
                  {timeAgo(run.created_at)} &middot; v{run.prompt_version}
                  {run.model ? ` &middot; ${run.model}` : ""}
                </div>
              </button>
            ))}
          </div>

          {/* Detail */}
          <div className="flex-1 min-w-0">
            {!selectedRun ? (
              <EmptyState
                icon={Play}
                title="Select a run"
                description="Choose a run from the list to see details."
              />
            ) : runDetail ? (
              <Card className="p-4">
                <pre className="text-[12px] text-[var(--color-text-secondary)] font-mono overflow-auto whitespace-pre-wrap">
                  {JSON.stringify(runDetail, null, 2)}
                </pre>
              </Card>
            ) : (
              <Spinner />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
