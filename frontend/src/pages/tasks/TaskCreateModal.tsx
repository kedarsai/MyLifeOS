import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { Toggle } from "@/components/ui/Toggle";
import { useGoals } from "@/api/hooks/useGoals";
import { useCapture, useProcessInbox } from "@/api/hooks/useEntries";

interface TaskCreateModalProps {
  open: boolean;
  onClose: () => void;
}

export function TaskCreateModal({ open, onClose }: TaskCreateModalProps) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [priority, setPriority] = useState("medium");
  const [goalId, setGoalId] = useState("");
  const [autoProcess, setAutoProcess] = useState(true);
  const [status, setStatus] = useState<"idle" | "capturing" | "processing" | "done">("idle");

  const { data: goalsData } = useGoals();
  const capture = useCapture();
  const processInbox = useProcessInbox();

  const goalOptions = (goalsData?.items ?? []).map((g) => ({
    value: g.goal_id,
    label: g.name,
  }));

  const reset = () => {
    setTitle("");
    setDueDate("");
    setPriority("medium");
    setGoalId("");
    setStatus("idle");
  };

  const handleCreate = async () => {
    // Format as a checklist item that sync_tasks_from_actions will parse
    // Include priority and due date in the text for the LLM/deterministic fallback
    let taskText = `- [ ] ${title.trim()}`;
    const meta: string[] = [];
    if (priority !== "medium") meta.push(`priority: ${priority}`);
    if (dueDate) meta.push(`due: ${dueDate}`);
    if (meta.length > 0) taskText += ` (${meta.join(", ")})`;

    setStatus("capturing");

    capture.mutate(
      {
        raw_text: taskText,
        type: "todo",
        goals: goalId ? [goalId] : [],
      },
      {
        onSuccess: (captureResult) => {
          if (autoProcess) {
            setStatus("processing");
            processInbox.mutate([captureResult.entry_id], {
              onSuccess: () => {
                setStatus("done");
                setTimeout(() => {
                  reset();
                  onClose();
                }, 600);
              },
              onError: () => {
                // Entry was captured even if processing failed
                setStatus("done");
                setTimeout(() => {
                  reset();
                  onClose();
                }, 600);
              },
            });
          } else {
            setStatus("done");
            setTimeout(() => {
              reset();
              onClose();
            }, 600);
          }
        },
      },
    );
  };

  const isPending = status === "capturing" || status === "processing";

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!isPending) {
          reset();
          onClose();
        }
      }}
      title="Create Task"
      size="md"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            loading={isPending}
            disabled={!title.trim()}
          >
            {status === "capturing"
              ? "Capturing..."
              : status === "processing"
                ? "Processing..."
                : status === "done"
                  ? "Done!"
                  : "Create Task"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label="Task Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g., Review project proposal"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && title.trim()) handleCreate();
          }}
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Due Date"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
          <Select
            label="Priority"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            options={[
              { value: "high", label: "High" },
              { value: "medium", label: "Medium" },
              { value: "low", label: "Low" },
            ]}
          />
        </div>

        <Select
          label="Goal"
          options={goalOptions}
          placeholder="None"
          value={goalId}
          onChange={(e) => setGoalId(e.target.value)}
        />

        <Toggle
          checked={autoProcess}
          onChange={setAutoProcess}
          label="Auto-process (create task immediately)"
        />

        {!autoProcess && (
          <p className="text-[11px] text-[var(--color-text-tertiary)]">
            Entry will be added to your inbox. Process it later to create the
            task.
          </p>
        )}
      </div>
    </Modal>
  );
}
