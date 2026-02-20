import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { timeAgo, truncate } from "@/lib/formatters";
import type { Entry } from "@/api/types";

interface InboxItemProps {
  entry: Entry;
}

export function InboxItem({ entry }: InboxItemProps) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <Badge
          className="capitalize"
          style={{
            backgroundColor: `var(--color-type-${entry.type}-bg)`,
            color: `var(--color-type-${entry.type}-text)`,
          }}
        >
          {entry.type}
        </Badge>
        <span className="text-[11px] text-[var(--color-text-tertiary)]">
          {timeAgo(entry.created_at)}
        </span>
      </div>

      {entry.summary && (
        <p className="text-[13px] font-medium text-[var(--color-text-primary)] mb-1">
          {entry.summary}
        </p>
      )}

      <p className="text-[12px] text-[var(--color-text-secondary)] leading-relaxed">
        {truncate(entry.raw_text, 200)}
      </p>

      {entry.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {entry.tags.map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      )}
    </Card>
  );
}
