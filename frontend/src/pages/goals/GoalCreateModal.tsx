import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Button } from "@/components/ui/Button";
import { useCreateGoal } from "@/api/hooks/useGoals";

interface GoalCreateModalProps {
  open: boolean;
  onClose: () => void;
}

export function GoalCreateModal({ open, onClose }: GoalCreateModalProps) {
  const createGoal = useCreateGoal();
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [endDate, setEndDate] = useState("");
  const [rulesMd, setRulesMd] = useState("");
  const [metrics, setMetrics] = useState("");
  const [status, setStatus] = useState("active");
  const [cadence, setCadence] = useState("7");

  const handleSubmit = () => {
    createGoal.mutate(
      {
        name,
        start_date: startDate,
        end_date: endDate || null,
        rules_md: rulesMd,
        metrics: metrics
          .split(",")
          .map((m) => m.trim())
          .filter(Boolean),
        status,
        review_cadence_days: parseInt(cadence) || 7,
      },
      {
        onSuccess: () => {
          onClose();
          setName("");
          setRulesMd("");
          setMetrics("");
        },
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Goal"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            loading={createGoal.isPending}
            disabled={!name.trim()}
          >
            Create
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Get Fit in 2026"
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Start Date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <Input
            label="End Date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <Textarea
          label="Rules (Markdown)"
          value={rulesMd}
          onChange={(e) => setRulesMd(e.target.value)}
          placeholder="Rules and guidelines for this goal..."
        />
        <Input
          label="Metrics (comma-separated)"
          value={metrics}
          onChange={(e) => setMetrics(e.target.value)}
          placeholder="steps, sleep, weight"
        />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[
              { value: "active", label: "Active" },
              { value: "paused", label: "Paused" },
            ]}
          />
          <Input
            label="Review Cadence (days)"
            type="number"
            min={1}
            max={365}
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
          />
        </div>
      </div>
    </Modal>
  );
}
