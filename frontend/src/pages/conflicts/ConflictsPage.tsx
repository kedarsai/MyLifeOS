import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/cn";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { timeAgo } from "@/lib/formatters";
import type { Conflict } from "@/api/types";

export default function ConflictsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<{
    items: Conflict[];
    total: number;
  }>({
    queryKey: ["conflicts"],
    queryFn: () => apiFetch("/conflicts"),
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  const { data: detail } = useQuery<Conflict>({
    queryKey: ["conflicts", selectedId],
    queryFn: () => apiFetch(`/conflicts/${selectedId}`),
    enabled: !!selectedId,
  });

  const resolve = useMutation({
    mutationFn: (action: string) =>
      apiFetch(`/conflicts/${selectedId}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          action,
          actor: "spa_user",
          notes: notes || undefined,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["conflicts"] });
      setSelectedId(null);
      setNotes("");
    },
  });

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Conflicts" />

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load conflicts: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={AlertTriangle}
          title="No conflicts"
          description="No vault/app conflicts detected."
        />
      )}

      {data && data.items.length > 0 && (
        <div className="flex flex-1 gap-4 min-h-0">
          {/* Conflict list */}
          <div className="w-80 shrink-0 overflow-y-auto scrollbar flex flex-col gap-1">
            {data.items.map((conflict) => (
              <button
                key={conflict.conflict_id}
                onClick={() => {
                  setSelectedId(conflict.conflict_id);
                  setNotes("");
                }}
                className={cn(
                  "text-left px-3 py-2 rounded-md transition-colors cursor-pointer",
                  selectedId === conflict.conflict_id
                    ? "bg-[var(--color-layer-active)]"
                    : "hover:bg-[var(--color-layer-hover)]",
                )}
              >
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      conflict.status === "open" ? "danger" : "default"
                    }
                  >
                    {conflict.status}
                  </Badge>
                  <span className="text-[13px] text-[var(--color-text-primary)] truncate">
                    {conflict.entity_type}/{conflict.field}
                  </span>
                </div>
                <div className="text-[11px] text-[var(--color-text-tertiary)] mt-0.5">
                  {timeAgo(conflict.created_at)}
                </div>
              </button>
            ))}
          </div>

          {/* Detail */}
          <div className="flex-1 min-w-0">
            {!selectedId || !detail ? (
              <EmptyState
                icon={AlertTriangle}
                title="Select a conflict"
                description="Choose a conflict from the list to resolve."
              />
            ) : (
              <Card className="p-4">
                <h3 className="text-[14px] font-semibold mb-3 text-[var(--color-text-primary)]">
                  {detail.entity_type} / {detail.field}
                </h3>

                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-1">
                      Vault Value
                    </div>
                    <pre className="text-[12px] bg-[var(--color-surface-tertiary)] rounded-md p-2 overflow-auto whitespace-pre-wrap">
                      {detail.vault_value}
                    </pre>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-1">
                      App Value
                    </div>
                    <pre className="text-[12px] bg-[var(--color-surface-tertiary)] rounded-md p-2 overflow-auto whitespace-pre-wrap">
                      {detail.app_value}
                    </pre>
                  </div>
                </div>

                {detail.status === "open" && (
                  <>
                    <Textarea
                      label="Resolution Notes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Optional notes..."
                      className="mb-3 min-h-[60px]"
                    />
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => resolve.mutate("keep_vault")}
                        loading={resolve.isPending}
                      >
                        Keep Vault
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => resolve.mutate("keep_app")}
                        loading={resolve.isPending}
                      >
                        Keep App
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => resolve.mutate("merge")}
                        loading={resolve.isPending}
                      >
                        Merge
                      </Button>
                    </div>
                  </>
                )}

                {detail.status === "resolved" && (
                  <div className="text-[12px] text-[var(--color-text-secondary)]">
                    Resolved: {detail.resolution} by {detail.resolved_by}
                    {detail.notes ? ` — ${detail.notes}` : ""}
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
