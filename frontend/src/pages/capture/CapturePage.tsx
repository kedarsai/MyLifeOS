import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Textarea } from "@/components/ui/Textarea";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useCapture, useBatchCapture, useInbox } from "@/api/hooks/useEntries";
import { useGoals } from "@/api/hooks/useGoals";
import { ENTRY_TYPES } from "@/lib/constants";
import type { CaptureResponse, BatchCaptureResponse } from "@/api/types";

type Tab = "single" | "batch";

const typeOptions = ENTRY_TYPES.map((t) => ({ value: t, label: t }));

export default function CapturePage() {
  const [tab, setTab] = useState<Tab>("single");
  const [rawText, setRawText] = useState("");
  const [entryType, setEntryType] = useState("note");
  const [tags, setTags] = useState("");
  const [selectedGoals, setSelectedGoals] = useState("");

  const capture = useCapture();
  const batchCapture = useBatchCapture();
  const { data: inboxData } = useInbox(1, 0); // just for count
  const { data: goalsData } = useGoals();

  const [lastResult, setLastResult] = useState<
    CaptureResponse | BatchCaptureResponse | null
  >(null);

  const goalOptions = (goalsData?.items ?? []).map((g) => ({
    value: g.goal_id,
    label: g.name,
  }));

  const handleCapture = () => {
    // When type is "todo", ensure raw_text is in checklist format so the
    // backend's task sync picks it up.  Each non-empty line that isn't
    // already a checkbox gets prefixed with "- [ ] ".
    let text = rawText;
    if (entryType === "todo") {
      const lines = rawText.split("\n").filter((l) => l.trim());
      text = lines
        .map((line) => {
          const trimmed = line.trim();
          // Already a checkbox line — keep as-is
          if (/^\s*-\s*\[[ xX]\]/.test(trimmed)) return trimmed;
          // Already a list item — wrap content in checkbox
          if (/^\s*-\s+/.test(trimmed))
            return `- [ ] ${trimmed.replace(/^\s*-\s+/, "")}`;
          // Plain text — wrap in checkbox
          return `- [ ] ${trimmed}`;
        })
        .join("\n");
    }

    const payload = {
      raw_text: text,
      type: entryType,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      goals: selectedGoals ? [selectedGoals] : [],
    };

    if (tab === "single") {
      capture.mutate(payload, {
        onSuccess: (data) => {
          setLastResult(data);
          setRawText("");
        },
      });
    } else {
      batchCapture.mutate(payload, {
        onSuccess: (data) => {
          setLastResult(data);
          setRawText("");
        },
      });
    }
  };

  const isPending = capture.isPending || batchCapture.isPending;

  return (
    <div className="max-w-xl mx-auto">
      <PageHeader title="Quick Capture" />

      {/* Tab toggle */}
      <div className="flex gap-1 mb-4 p-0.5 bg-[var(--color-surface-tertiary)] rounded-md w-fit">
        {(["single", "batch"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1 text-[13px] rounded-md transition-colors cursor-pointer ${
              tab === t
                ? "bg-[var(--color-surface-primary)] text-[var(--color-text-primary)] font-medium shadow-xs"
                : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
            }`}
          >
            {t === "single" ? "Single" : "Batch"}
          </button>
        ))}
      </div>

      {/* Input area */}
      <Textarea
        placeholder={
          entryType === "todo"
            ? tab === "single"
              ? "Enter a task, e.g. Do 15 push ups for the day"
              : "Enter tasks, one per line..."
            : tab === "single"
              ? "What's on your mind?"
              : "Enter multiple entries, separated by blank lines..."
        }
        value={rawText}
        onChange={(e) => setRawText(e.target.value)}
        className="min-h-[160px] mb-4"
        autoFocus
      />

      {/* Options row */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div className="w-32">
          <Select
            label="Type"
            options={typeOptions}
            value={entryType}
            onChange={(e) => setEntryType(e.target.value)}
          />
        </div>
        <div className="flex-1 min-w-[140px]">
          <Input
            label="Tags"
            placeholder="comma-separated"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
        </div>
        <div className="w-40">
          <Select
            label="Goal"
            options={goalOptions}
            placeholder="None"
            value={selectedGoals}
            onChange={(e) => setSelectedGoals(e.target.value)}
          />
        </div>
      </div>

      {/* Submit */}
      <Button
        onClick={handleCapture}
        loading={isPending}
        disabled={!rawText.trim()}
        className="w-full"
      >
        {tab === "single" ? "Capture" : "Batch Capture"}
      </Button>

      {/* Success feedback */}
      {lastResult && (
        <Card className="mt-4 p-4">
          <div className="flex items-start gap-2">
            <CheckCircle className="h-5 w-5 text-[var(--color-success)] shrink-0 mt-0.5" />
            <div>
              <p className="text-[13px] font-medium text-[var(--color-success)]">
                Captured!
              </p>
              {"entry_id" in lastResult && (
                <p className="text-[12px] text-[var(--color-text-secondary)] mt-1">
                  Entry {lastResult.entry_id}
                </p>
              )}
              {"count" in lastResult && (
                <p className="text-[12px] text-[var(--color-text-secondary)] mt-1">
                  {lastResult.count} entries created
                </p>
              )}
              {inboxData && inboxData.total > 0 && (
                <p className="text-[12px] text-[var(--color-text-secondary)] mt-1">
                  {inboxData.total} item{inboxData.total !== 1 ? "s" : ""} in
                  inbox &rarr;{" "}
                  <Link
                    to="/inbox"
                    className="text-[var(--color-text-link)] hover:underline"
                  >
                    Process
                  </Link>
                </p>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
