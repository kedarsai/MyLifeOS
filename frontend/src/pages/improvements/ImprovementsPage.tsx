import { TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Select";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { timeAgo } from "@/lib/formatters";
import type { Improvement } from "@/api/types";

const statusVariants: Record<string, "info" | "warning" | "success" | "default"> = {
  open: "info",
  in_progress: "warning",
  adopted: "success",
  dismissed: "default",
};

const statusOptions = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "adopted", label: "Adopted" },
  { value: "dismissed", label: "Dismissed" },
];

export default function ImprovementsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<{
    items: Improvement[];
    total: number;
  }>({
    queryKey: ["improvements"],
    queryFn: () => apiFetch("/improvements"),
  });

  const updateStatus = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: string;
    }) =>
      apiFetch(`/improvements/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["improvements"] });
    },
  });

  return (
    <div>
      <PageHeader title="Improvements" />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load improvements: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={TrendingUp}
          title="No improvements yet"
          description="Improvements are generated when processing inbox entries."
        />
      )}

      {data && data.items.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.items.map((item) => (
            <Card key={item.improvement_id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-[14px] font-medium text-[var(--color-text-primary)]">
                      {item.title}
                    </h3>
                    <Badge
                      variant={statusVariants[item.status] ?? "default"}
                    >
                      {item.status.replace("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-[12px] text-[var(--color-text-secondary)] line-clamp-2">
                    {item.rationale}
                  </p>
                  <span className="text-[11px] text-[var(--color-text-tertiary)] mt-1">
                    {timeAgo(item.created_at)}
                  </span>
                </div>
                <div className="w-32 shrink-0">
                  <Select
                    options={statusOptions}
                    value={item.status}
                    onChange={(e) =>
                      updateStatus.mutate({
                        id: item.improvement_id,
                        status: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
