import { useState } from "react";
import { Brain, ArrowLeft, MessageSquare } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { timeAgo } from "@/lib/formatters";
import { useAreas, useAreaTopics, useTopic, useHeatmap } from "@/api/hooks/useThoughts";
import type { ThoughtArea, ThoughtTopic } from "@/api/types";

function AreaCard({ area, onClick }: { area: ThoughtArea; onClick: () => void }) {
  return (
    <Card interactive onClick={onClick} className="p-4 cursor-pointer">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)]">
          {area.name}
        </h3>
        <Badge variant="default">{area.topic_count} topics</Badge>
      </div>
      {area.description && (
        <p className="text-[12px] text-[var(--color-text-secondary)] line-clamp-2">
          {area.description}
        </p>
      )}
      <div className="text-[11px] text-[var(--color-text-tertiary)] mt-2">
        {timeAgo(area.updated_at)}
      </div>
    </Card>
  );
}

function TopicList({ areaId, areaName, onSelect, onBack }: {
  areaId: string;
  areaName: string;
  onSelect: (id: string) => void;
  onBack: () => void;
}) {
  const { data, isLoading } = useAreaTopics(areaId);

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-3.5 w-3.5" />
        </Button>
        <h2 className="text-[14px] font-semibold text-[var(--color-text-primary)]">
          {areaName}
        </h2>
      </div>
      {isLoading && <Spinner />}
      {data && data.items.length === 0 && (
        <EmptyState icon={Brain} title="No topics yet" description="Topics will appear as entries are classified." />
      )}
      <div className="flex flex-col gap-2">
        {data?.items.map((topic: ThoughtTopic) => (
          <Card
            key={topic.topic_id}
            interactive
            onClick={() => onSelect(topic.topic_id)}
            className="p-3 cursor-pointer"
          >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-[var(--color-text-primary)]">
                {topic.name}
              </span>
              <Badge variant="outline">{topic.entry_count} entries</Badge>
            </div>
            {topic.description && (
              <p className="text-[12px] text-[var(--color-text-secondary)] mt-1">
                {topic.description}
              </p>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

function TopicDetailPanel({ topicId, onBack }: { topicId: string; onBack: () => void }) {
  const navigate = useNavigate();
  const { data, isLoading } = useTopic(topicId);

  if (isLoading) return <Spinner />;
  if (!data) return <div className="text-[13px] text-[var(--color-text-secondary)]">Topic not found.</div>;

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-3.5 w-3.5" />
        </Button>
        <h2 className="text-[14px] font-semibold text-[var(--color-text-primary)] flex-1">
          {data.name}
        </h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/chat?entity_type=thought_topic&entity_id=${topicId}`)}
        >
          <MessageSquare className="h-3.5 w-3.5 mr-1" />
          Chat
        </Button>
      </div>
      {data.description && (
        <p className="text-[13px] text-[var(--color-text-secondary)] mb-4">{data.description}</p>
      )}
      <h3 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-2">
        Linked Entries ({data.entries.length})
      </h3>
      <div className="flex flex-col gap-2">
        {data.entries.map((entry) => (
          <Card key={entry.id} className="p-3">
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-[var(--color-text-primary)]">{entry.summary || "Untitled"}</span>
              <Badge variant="info">{entry.type}</Badge>
            </div>
            <div className="text-[11px] text-[var(--color-text-tertiary)] mt-1">{timeAgo(entry.created_at)}</div>
          </Card>
        ))}
        {data.entries.length === 0 && (
          <p className="text-[12px] text-[var(--color-text-secondary)]">No entries linked yet.</p>
        )}
      </div>
    </div>
  );
}

function AttentionHeatmap() {
  const { data, isLoading } = useHeatmap(6);

  if (isLoading) return <Spinner />;
  if (!data || data.items.length === 0) return null;

  const months = [...new Set(data.items.map((c) => c.month))].sort();
  const areas = [...new Set(data.items.map((c) => c.area_name))].sort();
  const lookup = new Map(data.items.map((c) => [`${c.area_name}:${c.month}`, c.entry_count]));
  const maxCount = Math.max(...data.items.map((c) => c.entry_count), 1);

  return (
    <div className="mb-6">
      <h3 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase tracking-wider mb-2">
        Attention Heatmap
      </h3>
      <div className="overflow-x-auto">
        <table className="text-[11px]">
          <thead>
            <tr>
              <th className="pr-3 text-left text-[var(--color-text-tertiary)]">Area</th>
              {months.map((m) => (
                <th key={m} className="px-2 text-center text-[var(--color-text-tertiary)]">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {areas.map((area) => (
              <tr key={area}>
                <td className="pr-3 text-[var(--color-text-secondary)]">{area}</td>
                {months.map((month) => {
                  const count = lookup.get(`${area}:${month}`) || 0;
                  const intensity = count / maxCount;
                  return (
                    <td key={month} className="px-2 text-center">
                      <div
                        className="w-6 h-6 rounded mx-auto flex items-center justify-center text-[10px]"
                        style={{
                          backgroundColor: count > 0
                            ? `rgba(99, 102, 241, ${0.15 + intensity * 0.7})`
                            : "var(--color-surface-secondary)",
                          color: count > 0 ? "#fff" : "var(--color-text-tertiary)",
                        }}
                      >
                        {count || ""}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ThoughtsPage() {
  const { data, isLoading } = useAreas();
  const [selectedArea, setSelectedArea] = useState<{ id: string; name: string } | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Thoughts" />

      <AttentionHeatmap />

      {selectedTopic ? (
        <TopicDetailPanel
          topicId={selectedTopic}
          onBack={() => setSelectedTopic(null)}
        />
      ) : selectedArea ? (
        <TopicList
          areaId={selectedArea.id}
          areaName={selectedArea.name}
          onSelect={setSelectedTopic}
          onBack={() => setSelectedArea(null)}
        />
      ) : (
        <>
          {isLoading && <Spinner />}
          {data && data.items.length === 0 && (
            <EmptyState
              icon={Brain}
              title="No thought areas yet"
              description="Capture thoughts to auto-create areas and topics."
            />
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data?.items.map((area) => (
              <AreaCard
                key={area.area_id}
                area={area}
                onClick={() => setSelectedArea({ id: area.area_id, name: area.name })}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
