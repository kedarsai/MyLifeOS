import { useState } from "react";
import { Lightbulb, Plus, ArrowRight, MessageSquare, StickyNote } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { timeAgo } from "@/lib/formatters";
import { useIdeas, useIdea, useCreateIdea, useUpdateIdea, useConvertIdea } from "@/api/hooks/useIdeas";
import { EntryDetailModal } from "./EntryDetailModal";
import type { Idea, IdeaStatus } from "@/api/types";

const STATUS_TABS: { label: string; value: IdeaStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Raw", value: "raw" },
  { label: "Exploring", value: "exploring" },
  { label: "Mature", value: "mature" },
  { label: "Parked", value: "parked" },
  { label: "Dropped", value: "dropped" },
];

const STATUS_COLORS: Record<string, "default" | "success" | "warning" | "danger" | "info" | "outline"> = {
  raw: "default",
  exploring: "info",
  mature: "success",
  converted: "success",
  parked: "warning",
  dropped: "danger",
};

function IdeaCard({ idea, onClick }: { idea: Idea; onClick: () => void }) {
  return (
    <Card interactive onClick={onClick} className="p-4 cursor-pointer">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)] truncate flex-1 mr-2">
          {idea.title}
        </h3>
        <Badge variant={STATUS_COLORS[idea.status] || "default"}>{idea.status}</Badge>
      </div>
      {idea.description && (
        <p className="text-[12px] text-[var(--color-text-secondary)] line-clamp-2 mb-2">
          {idea.description}
        </p>
      )}
      <div className="flex items-center gap-3 text-[11px] text-[var(--color-text-tertiary)]">
        <span>{idea.entry_count} linked entries</span>
        <span>v{idea.version_no}</span>
        <span>{timeAgo(idea.updated_at)}</span>
      </div>
    </Card>
  );
}

function IdeaDetailPanel({ ideaId, onClose }: { ideaId: string; onClose: () => void }) {
  const navigate = useNavigate();
  const { data, isLoading } = useIdea(ideaId);
  const updateIdea = useUpdateIdea();
  const convertIdea = useConvertIdea();
  const [convertType, setConvertType] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<{ id: string; note: string } | null>(null);

  if (isLoading) return <Spinner />;
  if (!data) return <div className="text-[13px] text-[var(--color-text-secondary)]">Idea not found.</div>;

  const canConvert = data.status === "mature" && !data.converted_to_type;

  return (
    <>
      <Modal open onClose={onClose} title={data.title} size="lg">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge variant={STATUS_COLORS[data.status] || "default"}>{data.status}</Badge>
            {data.converted_to_type && (
              <span className="text-[12px] text-[var(--color-text-secondary)]">
                Converted to {data.converted_to_type}: {data.converted_to_id}
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              className="ml-auto"
              onClick={() => navigate(`/chat?entity_type=idea&entity_id=${ideaId}`)}
            >
              <MessageSquare className="h-3.5 w-3.5 mr-1" />
              Chat
            </Button>
          </div>

          {data.description && (
            <p className="text-[13px] text-[var(--color-text-secondary)]">{data.description}</p>
          )}

          {/* Status buttons */}
          {data.status !== "converted" && (
            <div className="flex gap-2 flex-wrap">
              {(["raw", "exploring", "mature", "parked", "dropped"] as IdeaStatus[])
                .filter((s) => s !== data.status)
                .map((s) => (
                  <Button
                    key={s}
                    variant="secondary"
                    size="sm"
                    onClick={() => updateIdea.mutate({ ideaId: data.idea_id, data: { status: s } })}
                    loading={updateIdea.isPending}
                  >
                    {s}
                  </Button>
                ))}
            </div>
          )}

          {/* Convert buttons */}
          {canConvert && (
            <div className="border-t border-[var(--color-border-subtle)] pt-3">
              <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-2">Convert to</h4>
              <div className="flex gap-2">
                {["goal", "project", "task"].map((t) => (
                  <Button
                    key={t}
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setConvertType(t);
                      convertIdea.mutate({ ideaId: data.idea_id, targetType: t });
                    }}
                    loading={convertIdea.isPending && convertType === t}
                  >
                    <ArrowRight className="h-3 w-3 mr-1" />
                    {t}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Linked entries */}
          <div>
            <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-2">
              Linked Entries ({data.entries.length})
            </h4>
            {data.entries.length === 0 ? (
              <p className="text-[12px] text-[var(--color-text-secondary)]">No entries linked.</p>
            ) : (
              <div className="flex flex-col gap-1">
                {data.entries.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between text-[12px] py-1.5 px-2 rounded-md cursor-pointer hover:bg-[var(--color-layer-hover)] transition-colors"
                    onClick={() => setSelectedEntry({ id: entry.id, note: entry.note })}
                  >
                    <div className="flex-1 min-w-0 mr-2">
                      <span className="text-[var(--color-text-primary)]">{entry.summary || "Untitled"}</span>
                      {entry.note && (
                        <span className="flex items-center gap-1 text-[11px] text-[var(--color-text-tertiary)] mt-0.5">
                          <StickyNote className="h-3 w-3 shrink-0" />
                          <span className="truncate">{entry.note}</span>
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline">{entry.link_type}</Badge>
                      <span className="text-[var(--color-text-tertiary)]">{timeAgo(entry.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Modal>

      {selectedEntry && (
        <EntryDetailModal
          entryId={selectedEntry.id}
          ideaId={ideaId}
          currentNote={selectedEntry.note}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </>
  );
}

function IdeaCreateModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const createIdea = useCreateIdea();

  const handleCreate = () => {
    if (!title.trim()) return;
    createIdea.mutate(
      { title: title.trim(), description: description.trim() },
      {
        onSuccess: () => {
          setTitle("");
          setDescription("");
          onClose();
        },
      },
    );
  };

  return (
    <Modal open={open} onClose={onClose} title="New Idea">
      <div className="space-y-3">
        <Input
          label="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What's the idea?"
          autoFocus
        />
        <div>
          <label className="block text-[12px] font-medium text-[var(--color-text-secondary)] mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the idea..."
            rows={3}
            className="w-full px-3 py-2 text-[13px] rounded-md bg-[var(--color-input-bg)] border border-[var(--color-input-border)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent resize-none"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={handleCreate} loading={createIdea.isPending} disabled={!title.trim()}>
            Create
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default function IdeasPage() {
  const [statusFilter, setStatusFilter] = useState<IdeaStatus | "">("");
  const { data, isLoading } = useIdeas(statusFilter || undefined);
  const [selectedIdea, setSelectedIdea] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        title="Ideas"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5 mr-1" /> New Idea
          </Button>
        }
      />

      {/* Status tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value as IdeaStatus | "")}
            className={`px-3 py-1.5 text-[12px] rounded-md transition-colors ${
              statusFilter === tab.value
                ? "bg-[var(--color-layer-active)] text-[var(--color-text-primary)] font-medium"
                : "text-[var(--color-text-secondary)] hover:bg-[var(--color-layer-hover)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && <Spinner />}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={Lightbulb}
          title="No ideas yet"
          description="Capture ideas from your notes or create one manually."
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-3.5 w-3.5 mr-1" /> New Idea
            </Button>
          }
        />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {data?.items.map((idea) => (
          <IdeaCard
            key={idea.idea_id}
            idea={idea}
            onClick={() => setSelectedIdea(idea.idea_id)}
          />
        ))}
      </div>

      {selectedIdea && (
        <IdeaDetailPanel ideaId={selectedIdea} onClose={() => setSelectedIdea(null)} />
      )}

      <IdeaCreateModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
