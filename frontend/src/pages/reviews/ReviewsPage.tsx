import { useState } from "react";
import { BarChart2, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useGoals } from "@/api/hooks/useGoals";
import { formatDate } from "@/lib/formatters";
import type { Review } from "@/api/types";

export default function ReviewsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<{
    items: Review[];
    total: number;
  }>({
    queryKey: ["reviews"],
    queryFn: () => apiFetch("/reviews"),
  });

  const { data: goalsData } = useGoals();
  const [genOpen, setGenOpen] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState("");

  const generateReview = useMutation({
    mutationFn: (goalId: string) =>
      apiFetch<Review>("/reviews/generate", {
        method: "POST",
        body: JSON.stringify({ goal_id: goalId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["reviews"] });
      setGenOpen(false);
    },
  });

  const goalOptions = (goalsData?.items ?? []).map((g) => ({
    value: g.goal_id,
    label: g.name,
  }));

  return (
    <div>
      <PageHeader
        title="Reviews"
        actions={
          <Button size="sm" onClick={() => setGenOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Generate Review
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
          Failed to load reviews: {(error as Error).message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={BarChart2}
          title="No reviews yet"
          description="Generate a weekly review for one of your goals."
          action={
            <Button size="sm" onClick={() => setGenOpen(true)}>
              Generate Review
            </Button>
          }
        />
      )}

      {data && data.items.length > 0 && (
        <div className="flex flex-col gap-4">
          {data.items.map((review) => (
            <Card key={review.review_id} className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="info">{review.goal_id}</Badge>
                <span className="text-[12px] text-[var(--color-text-secondary)]">
                  {formatDate(review.week_start)} &mdash;{" "}
                  {formatDate(review.week_end)}
                </span>
              </div>
              <pre className="text-[12px] text-[var(--color-text-secondary)] bg-[var(--color-surface-tertiary)] rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(review.review, null, 2)}
              </pre>
              <p className="text-[11px] text-[var(--color-text-tertiary)] mt-2">
                Created {formatDate(review.created_at)}
              </p>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={genOpen}
        onClose={() => setGenOpen(false)}
        title="Generate Review"
        footer={
          <>
            <Button variant="secondary" onClick={() => setGenOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => selectedGoal && generateReview.mutate(selectedGoal)}
              loading={generateReview.isPending}
              disabled={!selectedGoal}
            >
              Generate
            </Button>
          </>
        }
      >
        <Select
          label="Goal"
          options={goalOptions}
          placeholder="Select a goal..."
          value={selectedGoal}
          onChange={(e) => setSelectedGoal(e.target.value)}
        />
      </Modal>
    </div>
  );
}
