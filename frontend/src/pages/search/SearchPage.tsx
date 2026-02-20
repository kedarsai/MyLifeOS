import { useState } from "react";
import { Search } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useSearch } from "@/api/hooks/useSearch";
import { useDebounce } from "@/hooks/useDebounce";
import { timeAgo, truncate } from "@/lib/formatters";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const { data, isLoading } = useSearch({ q: debouncedQuery });

  return (
    <div>
      <PageHeader title="Search" />

      <div className="max-w-2xl mb-6">
        <Input
          placeholder="Search entries..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      {isLoading && debouncedQuery && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}

      {/* Facets */}
      {data?.facets &&
        Object.entries(data.facets).map(([facetName, facetValues]) => (
          <div key={facetName} className="flex flex-wrap gap-1.5 mb-3">
            {Object.entries(facetValues).map(([val, count]) => (
              <Badge key={val} variant="outline">
                {val} ({count})
              </Badge>
            ))}
          </div>
        ))}

      {/* Results */}
      {data && data.items.length === 0 && debouncedQuery && (
        <EmptyState
          icon={Search}
          title="No results"
          description={`Nothing found for "${debouncedQuery}"`}
        />
      )}

      {data && data.items.length > 0 && (
        <div className="flex flex-col gap-2">
          {data.items.map((item) => (
            <div
              key={item.id}
              className="p-3 rounded-md hover:bg-[var(--color-layer-hover)] transition-colors border-b border-[var(--color-border-subtle)]"
            >
              <div className="flex items-center gap-2 mb-1">
                <Badge
                  className="capitalize"
                  style={{
                    backgroundColor: `var(--color-type-${item.type}-bg)`,
                    color: `var(--color-type-${item.type}-text)`,
                  }}
                >
                  {item.type}
                </Badge>
                <span className="text-[11px] text-[var(--color-text-tertiary)]">
                  {timeAgo(item.created_at)}
                </span>
                {item.score != null && (
                  <span className="text-[10px] text-[var(--color-text-placeholder)]">
                    score: {item.score.toFixed(2)}
                  </span>
                )}
              </div>
              <p className="text-[13px] text-[var(--color-text-primary)]">
                {item.summary || truncate(item.raw_text, 160)}
              </p>
            </div>
          ))}
          <div className="text-[12px] text-[var(--color-text-tertiary)] mt-2">
            {data.total} result{data.total !== 1 ? "s" : ""} &middot; Page{" "}
            {data.page} of {data.total_pages}
          </div>
        </div>
      )}
    </div>
  );
}
