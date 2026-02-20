import { useState, useEffect } from "react";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/formatters";
import { useEntry, useUpdateEntryNote } from "@/api/hooks/useEntries";

interface Props {
  entryId: string;
  ideaId: string;
  currentNote: string;
  onClose: () => void;
}

export function EntryDetailModal({ entryId, ideaId, currentNote, onClose }: Props) {
  const { data, isLoading } = useEntry(entryId);
  const updateNote = useUpdateEntryNote();
  const [note, setNote] = useState(currentNote);
  const [saved, setSaved] = useState(true);

  useEffect(() => {
    setNote(currentNote);
    setSaved(true);
  }, [currentNote]);

  const handleSave = () => {
    updateNote.mutate(
      { ideaId, entryId, note },
      { onSuccess: () => setSaved(true) },
    );
  };

  if (isLoading) return <Modal open onClose={onClose} title="Loading..."><Spinner /></Modal>;
  if (!data) return <Modal open onClose={onClose} title="Not found"><p className="text-[13px]">Entry not found.</p></Modal>;

  return (
    <Modal open onClose={onClose} title={data.summary || "Untitled entry"} size="lg">
      <div className="space-y-4">
        {/* Meta badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="info">{data.type}</Badge>
          <Badge variant={data.status === "processed" ? "success" : "default"}>{data.status}</Badge>
          {data.tags.map((tag) => (
            <Badge key={tag} variant="outline">{tag}</Badge>
          ))}
          <span className="text-[11px] text-[var(--color-text-tertiary)] ml-auto">
            {timeAgo(data.created_at)}
          </span>
        </div>

        {/* Raw text */}
        {data.raw_text && (
          <div>
            <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-1">
              Raw Text
            </h4>
            <div className="text-[13px] text-[var(--color-text-primary)] whitespace-pre-wrap bg-[var(--color-canvas)] rounded-md p-3 border border-[var(--color-border-subtle)] leading-relaxed">
              {data.raw_text}
            </div>
          </div>
        )}

        {/* Details */}
        {data.details_md && data.details_md !== "-" && (
          <div>
            <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-1">
              Details
            </h4>
            <div className="text-[13px] text-[var(--color-text-secondary)] whitespace-pre-wrap leading-relaxed">
              {data.details_md}
            </div>
          </div>
        )}

        {/* Actions */}
        {data.actions_md && data.actions_md !== "-" && (
          <div>
            <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-1">
              Actions
            </h4>
            <div className="text-[13px] text-[var(--color-text-secondary)] whitespace-pre-wrap leading-relaxed">
              {data.actions_md}
            </div>
          </div>
        )}

        {/* Note textarea */}
        <div className="border-t border-[var(--color-border-subtle)] pt-3">
          <h4 className="text-[12px] font-medium text-[var(--color-text-tertiary)] uppercase mb-1">
            Note
          </h4>
          <textarea
            value={note}
            onChange={(e) => { setNote(e.target.value); setSaved(false); }}
            placeholder="Add a note about how this entry relates to the idea..."
            rows={3}
            className="w-full px-3 py-2 text-[13px] rounded-md bg-[var(--color-input-bg)] border border-[var(--color-input-border)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-placeholder)] focus:outline-none focus:ring-2 focus:ring-[var(--color-input-focus-ring)] focus:border-transparent resize-none"
          />
          <div className="flex items-center gap-2 mt-2">
            <Button
              size="sm"
              onClick={handleSave}
              loading={updateNote.isPending}
              disabled={saved}
            >
              Save Note
            </Button>
            {saved && note && (
              <span className="text-[11px] text-[var(--color-text-tertiary)]">Saved</span>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
