import { Badge } from "@/components/ui/Badge";
import { formatDate, truncate } from "@/lib/formatters";
import type { Entry } from "@/api/types";

interface TimelineItemProps {
  entry: Entry;
}

export function TimelineItem({ entry }: TimelineItemProps) {
  return (
    <div className="flex items-center gap-3 py-2 px-2.5 hover:bg-[var(--color-layer-hover)] rounded-md transition-colors">
      <Badge
        className="capitalize shrink-0 w-16 justify-center"
        style={{
          backgroundColor: `var(--color-type-${entry.type}-bg)`,
          color: `var(--color-type-${entry.type}-text)`,
        }}
      >
        {entry.type}
      </Badge>

      <span className="text-[12px] text-[var(--color-text-tertiary)] shrink-0 w-20">
        {formatDate(entry.created_at)}
      </span>

      <span className="text-[13px] text-[var(--color-text-primary)] min-w-0 flex-1 truncate">
        {entry.summary || truncate(entry.raw_text, 100)}
      </span>

      {entry.tags.length > 0 && (
        <div className="flex gap-1 shrink-0">
          {entry.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
