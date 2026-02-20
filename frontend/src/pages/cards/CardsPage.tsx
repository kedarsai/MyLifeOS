import { useState } from "react";
import { CreditCard } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { timeAgo } from "@/lib/formatters";
import { useCards, useCard } from "@/api/hooks/useCards";
import type { InsightCard } from "@/api/types";

const ENTITY_TYPE_OPTIONS = [
  { label: "All", value: "" },
  { label: "Goal", value: "goal" },
  { label: "Topic", value: "thought_topic" },
  { label: "Idea", value: "idea" },
];

function CardItem({ card, onClick }: { card: InsightCard; onClick: () => void }) {
  return (
    <Card interactive onClick={onClick} className="p-4 cursor-pointer">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)] truncate flex-1 mr-2">
          {card.title}
        </h3>
        <Badge variant="info">{card.entity_type}</Badge>
      </div>
      <p className="text-[12px] text-[var(--color-text-secondary)] line-clamp-3 mb-2">
        {card.body_md}
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        {card.tags.map((tag) => (
          <Badge key={tag} variant="outline">{tag}</Badge>
        ))}
        <span className="text-[11px] text-[var(--color-text-tertiary)] ml-auto">
          {timeAgo(card.created_at)}
        </span>
      </div>
    </Card>
  );
}

function CardDetailModal({ cardId, onClose }: { cardId: string; onClose: () => void }) {
  const { data, isLoading } = useCard(cardId);

  if (isLoading) return <Modal open onClose={onClose} title="Loading..."><Spinner /></Modal>;
  if (!data) return <Modal open onClose={onClose} title="Not found"><p>Card not found.</p></Modal>;

  return (
    <Modal open onClose={onClose} title={data.title} size="lg">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant="info">{data.entity_type}</Badge>
          <span className="text-[12px] text-[var(--color-text-tertiary)]">
            Entity: {data.entity_id}
          </span>
        </div>

        <div className="text-[13px] text-[var(--color-text-primary)] whitespace-pre-wrap leading-relaxed">
          {data.body_md}
        </div>

        {data.action_taken && (
          <div className="border-t border-[var(--color-border-subtle)] pt-3">
            <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-1">
              Action Taken
            </h4>
            <p className="text-[12px] text-[var(--color-text-secondary)]">{data.action_taken}</p>
          </div>
        )}

        {data.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {data.tags.map((tag) => (
              <Badge key={tag} variant="outline">{tag}</Badge>
            ))}
          </div>
        )}

        <div className="text-[11px] text-[var(--color-text-tertiary)]">
          v{data.version_no} &middot; {timeAgo(data.created_at)}
        </div>
      </div>
    </Modal>
  );
}

export default function CardsPage() {
  const [entityFilter, setEntityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const { data, isLoading } = useCards({
    entity_type: entityFilter || undefined,
    q: searchQuery || undefined,
  });
  const [selectedCard, setSelectedCard] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Insight Cards" />

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex gap-1">
          {ENTITY_TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setEntityFilter(opt.value)}
              className={`px-3 py-1.5 text-[12px] rounded-md transition-colors ${
                entityFilter === opt.value
                  ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)] font-medium"
                  : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex-1 max-w-xs">
          <Input
            placeholder="Search cards..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSearchQuery(search);
            }}
          />
        </div>
      </div>

      {isLoading && <Spinner />}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={CreditCard}
          title="No insight cards"
          description="Cards are created from chat conversations."
        />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {data?.items.map((card) => (
          <CardItem
            key={card.card_id}
            card={card}
            onClick={() => setSelectedCard(card.card_id)}
          />
        ))}
      </div>

      {selectedCard && (
        <CardDetailModal cardId={selectedCard} onClose={() => setSelectedCard(null)} />
      )}
    </div>
  );
}
