import { useSearchParams } from "react-router-dom";
import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Select } from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { TimelineItem } from "./TimelineItem";
import { useTimeline } from "@/api/hooks/useEntries";
import { useGoals } from "@/api/hooks/useGoals";
import { ENTRY_TYPES } from "@/lib/constants";
import type { Entry } from "@/api/types";

const typeOptions = ENTRY_TYPES.map((t) => ({ value: t, label: t }));

function groupByMonth(items: Entry[]): Record<string, Entry[]> {
  const groups: Record<string, Entry[]> = {};
  for (const item of items) {
    const key = item.created_at.slice(0, 7); // YYYY-MM
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}

function formatMonthKey(key: string): string {
  const [year, month] = key.split("-");
  const date = new Date(Number(year), Number(month) - 1);
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export default function TimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = {
    page: parseInt(searchParams.get("page") ?? "1"),
    page_size: 20,
    type: searchParams.get("type") ?? undefined,
    tag: searchParams.get("tag") ?? undefined,
    goal: searchParams.get("goal") ?? undefined,
    date_from: searchParams.get("date_from") ?? undefined,
    date_to: searchParams.get("date_to") ?? undefined,
  };

  const { data, isLoading, error } = useTimeline(filters);
  const { data: goalsData } = useGoals();

  const goalOptions = (goalsData?.items ?? []).map((g) => ({
    value: g.goal_id,
    label: g.name,
  }));

  const updateParam = (key: string, val: string) => {
    const next = new URLSearchParams(searchParams);
    if (val) next.set(key, val);
    else next.delete(key);
    next.delete("page"); // reset to page 1 on filter change
    setSearchParams(next, { replace: true });
  };

  const setPage = (p: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(p));
    setSearchParams(next, { replace: true });
  };

  const grouped = data ? groupByMonth(data.items) : {};

  return (
    <div>
      <PageHeader title="Timeline" />

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div className="w-32">
          <Select
            options={typeOptions}
            placeholder="All types"
            value={filters.type ?? ""}
            onChange={(e) => updateParam("type", e.target.value)}
          />
        </div>
        <div className="w-36">
          <Input
            placeholder="Tag..."
            value={filters.tag ?? ""}
            onChange={(e) => updateParam("tag", e.target.value)}
          />
        </div>
        <div className="w-40">
          <Select
            options={goalOptions}
            placeholder="All goals"
            value={filters.goal ?? ""}
            onChange={(e) => updateParam("goal", e.target.value)}
          />
        </div>
        <div className="w-36">
          <Input
            type="date"
            placeholder="From"
            value={filters.date_from ?? ""}
            onChange={(e) => updateParam("date_from", e.target.value)}
          />
        </div>
        <div className="w-36">
          <Input
            type="date"
            placeholder="To"
            value={filters.date_to ?? ""}
            onChange={(e) => updateParam("date_to", e.target.value)}
          />
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {error && (
        <div className="text-[13px] text-[var(--color-danger)] py-4">
          Failed to load timeline: {error.message}
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={ArrowRight}
          title="No entries found"
          description="Try adjusting your filters or capture something new."
        />
      )}

      {data && data.items.length > 0 && (
        <>
          {Object.entries(grouped).map(([monthKey, items]) => (
            <div key={monthKey} className="mb-6">
              <div className="sticky top-0 z-10 bg-[var(--color-canvas)] py-2">
                <h3 className="text-[12px] font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] border-b border-[var(--color-border-subtle)] pb-1">
                  {formatMonthKey(monthKey)}
                </h3>
              </div>
              <div className="flex flex-col">
                {items.map((entry) => (
                  <TimelineItem key={entry.id} entry={entry} />
                ))}
              </div>
            </div>
          ))}

          {/* Pagination */}
          <div className="flex items-center justify-center gap-3 mt-4 py-4">
            <Button
              variant="secondary"
              size="sm"
              disabled={filters.page <= 1}
              onClick={() => setPage(filters.page - 1)}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </Button>
            <span className="text-[12px] text-[var(--color-text-tertiary)]">
              Page {data.page} of {data.total_pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={filters.page >= data.total_pages}
              onClick={() => setPage(filters.page + 1)}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
